"""Run: python -m unittest discover -s backend/tests -v (from repository root)."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db
import migrations
import records
from flask import Flask
from PIL import Image
from routes import api_bp

HEADERS = {'X-App-Version': '2'}


def signature():
    image = Image.new('RGB', (400, 200), 'white')
    image.putpixel((1, 1), (0, 0, 0))
    output = io.BytesIO()
    image.save(output, format='PNG')
    return records.SIGNATURE_PREFIX + base64.b64encode(output.getvalue()).decode()


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_path = db.DB_PATH
        db.DB_PATH = str(Path(self.temp.name) / 'test.db')
        db.init_db()
        for emp_id, name in [('A','One'), ('B','Two'), ('C','Three')]:
            db.insert_single_employee(emp_id,name,'Team','G4','01012340000')
        app = Flask(__name__)
        app.register_blueprint(api_bp, url_prefix='/api')
        app.testing = True
        self.app = app
        self.client = app.test_client()
        self.round_id = self.post('/admin/rounds', {'name':'2026 H2'}).json['round_id']
        self.project = db.create_evaluation_project(1,round_id=self.round_id)
        db.add_evaluator_to_project(self.project,2)
        conn = db.get_db_connection()
        self.assignment = conn.execute('SELECT id FROM evaluation_assignments').fetchone()[0]
        conn.close()
        self.questions = self.client.get(f'/api/evaluations/questions?assignment_id={self.assignment}').json

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp.cleanup()

    def post(self, path, payload):
        return self.client.post('/api'+path, json=payload, headers=HEADERS)

    def payload(self):
        return {'assignment_id':self.assignment,'evaluator_id':2,'evaluatee_id':1,
                'question_revision':self.questions[0]['question_revision'], 'signature_data':signature(),
                'answers':[{'question_id':q['id'],'score':None if q['is_essay'] else 8,
                            'answer_text':'Opinion' if q['is_essay'] else ''} for q in self.questions]}

    def detail(self):
        return self.client.get(f'/api/admin/evaluations/{self.assignment}').json

    def test_new_round_keeps_old_period_and_answers(self):
        self.assertEqual(self.post('/evaluations/submit',self.payload()).status_code,200)
        before = self.detail()
        round_id = self.post('/admin/rounds', {'name':'2027 H1'}).json['round_id']
        new_project = db.create_evaluation_project(1,round_id=round_id,start_date='2027-01-01',end_date='2027-01-31')
        self.assertNotEqual(new_project,self.project)
        self.assertEqual(self.detail(),before)
        with self.assertRaises(ValueError):
            db.create_evaluation_project(1,round_id=self.round_id)

    def test_snapshot_survives_template_and_employee_changes(self):
        self.assertEqual(self.post('/evaluations/submit',self.payload()).status_code,200)
        before = self.detail()
        db.update_employee_info('A','Changed','Other','G1','')
        conn = db.get_db_connection()
        conn.execute("UPDATE evaluation_questions SET question_text='Changed',is_essay=1,is_active=0")
        conn.commit();conn.close()
        self.assertEqual(self.detail(),before)

    def test_other_type_never_appears_in_pdf_data(self):
        self.post('/admin/questions',{'question_text':'Other type','category':'Other','is_essay':0,'evaluation_type':'직무능력 평가'})
        self.assertEqual(len(self.detail()['questions']),len(self.questions))
        self.assertEqual(self.detail()['max_score'],30)

    def test_export_keeps_pending_and_null_team_and_duplicate_labels(self):
        conn = db.get_db_connection()
        conn.execute('UPDATE employees SET team_name=NULL,position=NULL WHERE id=2')
        conn.execute("UPDATE evaluation_questions SET question_text='Same' WHERE is_essay=0")
        conn.commit();conn.close()
        db.add_evaluator_to_project(self.project,3)
        self.assertEqual(self.post('/evaluations/submit',self.payload()).status_code,200)
        df = db.get_evaluation_results_for_export()
        self.assertEqual(len(df),2)
        self.assertEqual(df.loc[df['배정 ID']==self.assignment,'평가 총점'].iloc[0],24)
        self.assertEqual(len([c for c in df.columns if c.startswith('[Q')]),4)

    def test_deactivate_question_keeps_export_and_frozen_form(self):
        self.post('/evaluations/submit',self.payload())
        before = db.get_evaluation_results_for_export().to_json()
        response = self.client.delete(f"/api/admin/questions/{self.questions[0]['id']}",headers=HEADERS)
        self.assertEqual(response.status_code,200)
        self.assertEqual(db.get_evaluation_results_for_export().to_json(),before)

    def test_phone_is_returned_and_omitted_phone_is_preserved(self):
        employee = self.client.get('/api/admin/employees').json[0]
        self.assertEqual(employee['phone'],'01012340000')
        self.assertEqual(self.client.put('/api/admin/employees/A',json={'name':'Edited'},headers=HEADERS).status_code,200)
        self.assertEqual(db.get_employee_by_emp_id('A')['phone'],'01012340000')
        self.client.put('/api/admin/employees/A',json={'name':'Edited','phone':''},headers=HEADERS)
        self.assertEqual(db.get_employee_by_emp_id('A')['phone'],'')

    def test_reject_invalid_final_payloads_without_changing_draft(self):
        valid = self.payload()
        self.assertEqual(self.post('/evaluations/draft',valid).status_code,200)
        conn=db.get_db_connection();before=migrations.fingerprints(conn);conn.close()
        invalids = []
        for key,value in [('evaluator_id',3),('evaluatee_id',3),('assignment_id',True),('answers',[]),
                          ('signature_data',None),('signature_data','data:image/svg+xml,<svg/>'),('question_revision','old')]:
            bad = json.loads(json.dumps(valid));bad[key]=value;invalids.append(bad)
        for score in [0,5,11,999,'8',True]:
            bad=json.loads(json.dumps(valid));bad['answers'][0]['score']=score;invalids.append(bad)
        bad=json.loads(json.dumps(valid));bad['answers'].append(bad['answers'][0]);invalids.append(bad)
        bad=json.loads(json.dumps(valid));bad['answers'][-1]['answer_text']='x'*1001;invalids.append(bad)
        bad=json.loads(json.dumps(valid));bad['answers'][0]['question_id']=99999;invalids.append(bad)
        for bad in invalids:
            with self.subTest(keys=list(bad)):
                self.assertIn(self.post('/evaluations/submit',bad).status_code,(400,409))
        conn=db.get_db_connection();self.assertEqual(migrations.fingerprints(conn),before);conn.close()

    def test_period_bounds_and_invalid_dates(self):
        conn=db.get_db_connection();conn.execute("UPDATE evaluation_projects SET start_date='2099-01-01',end_date=NULL");conn.commit();conn.close()
        self.assertEqual(self.post('/evaluations/submit',self.payload()).status_code,409)
        self.assertEqual(self.client.get('/api/evaluations/assignments?evaluator_id=2').json,[])
        response=self.client.patch(f'/api/admin/projects/{self.project}/period',json={'start_date':'2027-02-02','end_date':'2027-01-01'},headers=HEADERS)
        self.assertEqual(response.status_code,400)

    def test_final_cannot_be_reopened_deleted_or_reset(self):
        self.post('/evaluations/submit',self.payload())
        self.assertEqual(self.post('/evaluations/draft',self.payload()).status_code,409)
        self.assertEqual(self.client.patch(f'/api/admin/assignments/{self.assignment}/status',json={'status':'saved'},headers=HEADERS).status_code,409)
        self.assertEqual(self.client.delete(f'/api/admin/assignments/{self.assignment}',headers=HEADERS).status_code,409)
        self.assertNotEqual(self.client.delete(f'/api/admin/projects/{self.project}',headers=HEADERS).status_code,200)
        self.assertNotEqual(self.post('/admin/employees/reset',{}).status_code,200)
        self.assertEqual(len(self.detail()['answers']),len(self.questions))

    def test_concurrent_submits_cannot_overwrite_final(self):
        payload=self.payload();results=[];barrier=threading.Barrier(2)
        def submit():
            with self.app.test_client() as client:
                barrier.wait()
                results.append(client.post('/api/evaluations/submit',json=payload,headers=HEADERS).status_code)
        threads=[threading.Thread(target=submit) for _ in range(2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(sorted(results),[200,409])

    def test_cached_form_and_maintenance_block_writes(self):
        self.assertEqual(self.client.post('/api/evaluations/submit',json=self.payload()).status_code,409)
        Path(db.DB_PATH+'.maintenance').touch()
        self.assertEqual(self.post('/evaluations/draft',self.payload()).status_code,503)
        self.assertEqual(self.client.post('/api/auth/login',json={'emp_id':'B'}).status_code,503)

    def test_blank_signature_is_rejected_and_draft_kept(self):
        payload=self.payload()
        self.post('/evaluations/draft',payload)
        image=Image.new('RGBA',(400,200),(255,255,255,0));output=io.BytesIO();image.save(output,format='PNG')
        payload['signature_data']=records.SIGNATURE_PREFIX+base64.b64encode(output.getvalue()).decode()
        self.assertEqual(self.post('/evaluations/submit',payload).status_code,400)
        self.assertEqual(self.detail()['assignment']['status'],'saved')

    def test_excel_download_keeps_formula_looking_answers_as_text(self):
        from openpyxl import load_workbook
        payload=self.payload();payload['answers'][-1]['answer_text']='=1+1'
        self.post('/evaluations/submit',payload)
        response=self.client.get('/api/admin/results/export')
        self.assertEqual(response.status_code,200)
        workbook=load_workbook(io.BytesIO(response.data))
        matching=[cell for row in workbook.active for cell in row if cell.value=='=1+1']
        self.assertEqual(len(matching),1)
        self.assertEqual(matching[0].data_type,'s')

    def test_import_preview_and_org_reset_do_not_erase_phone(self):
        import pandas as pd
        data=[['']*53 for _ in range(2)]
        data[0][4:7]=['Dept','Office A','Team A'];data[0][11:13]=['A','One'];data[0][15]='G4'
        data[1][5]='Office B';data[1][11:13]=['B','Two'];data[1][15]='G4'
        with patch.object(pd,'read_excel',return_value=pd.DataFrame(data)):
            preview=db.preview_employees_from_excel('mock.xlsx')
            self.assertEqual(db.get_employee_by_emp_id('B')['team_name'],'Team')
            db.upsert_employees_from_excel('mock.xlsx',preview['preview_token'])
        self.assertEqual(db.get_employee_by_emp_id('B')['team_name'],'Office B')
        self.assertEqual(db.get_employee_by_emp_id('B')['phone'],'01012340000')

    def test_stale_import_preview_rolls_back(self):
        import pandas as pd
        data=[['']*53];data[0][11:13]=['A','One'];data[0][15]='G4'
        with patch.object(pd,'read_excel',return_value=pd.DataFrame(data)):
            preview=db.preview_employees_from_excel('mock.xlsx')
            db.update_employee_info('A','Concurrent','Other','G1',None)
            with self.assertRaises(ValueError):db.upsert_employees_from_excel('mock.xlsx',preview['preview_token'])
        self.assertEqual(db.get_employee_by_emp_id('A')['name'],'Concurrent')

    def test_upload_filename_cannot_select_filesystem_path(self):
        with patch.object(db,'preview_employees_from_excel',return_value={'ok':True}) as preview:
            response=self.client.post('/api/admin/upload-excel?preview=1',data={'file':(io.BytesIO(b'fake'),'../../outside.xlsx')},headers=HEADERS)
        self.assertEqual(response.status_code,200)
        saved=Path(preview.call_args.args[0])
        self.assertEqual(saved.parent,Path(__file__).resolve().parents[1]/'temp')
        self.assertNotIn('outside',saved.name)
        self.assertFalse(saved.exists())


class MigrationTests(unittest.TestCase):
    def legacy_fixture(self,path,broken=False):
        conn=sqlite3.connect(path)
        conn.executescript('''
            CREATE TABLE employees(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,emp_id TEXT UNIQUE,team_name TEXT,position TEXT,phone TEXT);
            INSERT INTO employees VALUES(1,'One','A','Team','G4','010'),(2,'Two','B',NULL,'G4','020');
            CREATE TABLE evaluation_questions(id INTEGER PRIMARY KEY,question_text TEXT,category TEXT,is_essay INTEGER);
            INSERT INTO evaluation_questions VALUES(1,'Old question','Cat',0);
            CREATE TABLE evaluation_assignments(id INTEGER PRIMARY KEY AUTOINCREMENT,evaluator_id INTEGER,evaluatee_id INTEGER NOT NULL,status TEXT,assigned_at TEXT,UNIQUE(evaluator_id,evaluatee_id));
            INSERT INTO evaluation_assignments VALUES(7,2,1,'completed','2020-01-01');
            CREATE TABLE evaluations(id INTEGER PRIMARY KEY AUTOINCREMENT,assignment_id INTEGER UNIQUE,evaluator_id INTEGER,evaluatee_id INTEGER,submitted_at TEXT,FOREIGN KEY(assignment_id) REFERENCES evaluation_assignments(id) ON DELETE CASCADE);
            INSERT INTO evaluations VALUES(9,7,2,1,'2020-01-01');
            CREATE TABLE evaluation_answers(id INTEGER PRIMARY KEY AUTOINCREMENT,evaluation_id INTEGER,question_id INTEGER,score INTEGER,answer_text TEXT,FOREIGN KEY(evaluation_id) REFERENCES evaluations(id) ON DELETE CASCADE,FOREIGN KEY(question_id) REFERENCES evaluation_questions(id));
            INSERT INTO evaluation_answers VALUES(11,9,1,3,'unchanged');
        ''')
        if broken:conn.execute('UPDATE evaluation_answers SET question_id=999')
        conn.commit();conn.close()

    def test_legacy_migration_preserves_answers_and_scores_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/'old.db');self.legacy_fixture(path)
            conn=sqlite3.connect(path);conn.row_factory=sqlite3.Row;before=migrations.fingerprints(conn);conn.close()
            result=migrations.migrate(path)
            self.assertTrue(Path(result['backup']).is_file())
            conn=sqlite3.connect(path);conn.row_factory=sqlite3.Row
            migrations.verify_preserved(conn,before)
            self.assertEqual(conn.execute('SELECT score FROM evaluation_answers').fetchone()[0],3)
            self.assertIsNotNone(conn.execute('SELECT record_snapshot FROM evaluations').fetchone()[0])
            conn.close()
            self.assertFalse(migrations.migrate(path)['changed'])

    def test_failed_upgrade_rolls_back_every_table_and_keeps_backup(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/'old.db');self.legacy_fixture(path,broken=True)
            conn=sqlite3.connect(path);conn.row_factory=sqlite3.Row;before=migrations.fingerprints(conn);schema=conn.execute('SELECT sql FROM sqlite_master ORDER BY name').fetchall();conn.close()
            with self.assertRaises(RuntimeError):migrations.migrate(path)
            conn=sqlite3.connect(path);conn.row_factory=sqlite3.Row
            self.assertEqual(migrations.fingerprints(conn),before)
            self.assertEqual(conn.execute('SELECT sql FROM sqlite_master ORDER BY name').fetchall(),schema)
            conn.close()
            self.assertEqual(len(list((Path(td)/'db_backups').glob('*.sqlite3'))),1)

    def test_startup_refuses_unmigrated_db_without_touching_it(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'old.db';self.legacy_fixture(path)
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(RuntimeError):migrations.ensure_ready(str(path))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)

    def test_broken_old_assignment_reference_is_repaired_without_losing_children(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/'old.db');self.legacy_fixture(path)
            conn=sqlite3.connect(path)
            conn.execute('ALTER TABLE evaluations RENAME TO evaluations_old')
            conn.executescript('''CREATE TABLE evaluations(id INTEGER PRIMARY KEY AUTOINCREMENT,assignment_id INTEGER UNIQUE,
                evaluator_id INTEGER,evaluatee_id INTEGER,submitted_at TEXT,
                FOREIGN KEY(assignment_id) REFERENCES evaluation_assignments_old(id) ON DELETE CASCADE);
                INSERT INTO evaluations SELECT * FROM evaluations_old;
                DROP TABLE evaluations_old;
                CREATE TABLE answers_repaired(id INTEGER PRIMARY KEY AUTOINCREMENT,evaluation_id INTEGER,question_id INTEGER,
                    score INTEGER,answer_text TEXT,FOREIGN KEY(evaluation_id) REFERENCES evaluations(id) ON DELETE CASCADE,
                    FOREIGN KEY(question_id) REFERENCES evaluation_questions(id));
                INSERT INTO answers_repaired SELECT * FROM evaluation_answers;
                DROP TABLE evaluation_answers;
                ALTER TABLE answers_repaired RENAME TO evaluation_answers;
                UPDATE sqlite_sequence SET seq=90 WHERE name='evaluations';
                UPDATE sqlite_sequence SET seq=80 WHERE name='evaluation_assignments';''')
            conn.commit();conn.close()
            migrations.migrate(path)
            conn=sqlite3.connect(path);conn.row_factory=sqlite3.Row
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(),[])
            self.assertEqual(conn.execute('SELECT id,score FROM evaluation_answers').fetchone()[:],(11,3))
            self.assertEqual(conn.execute("SELECT seq FROM sqlite_sequence WHERE name='evaluations'").fetchone()[0],90)
            self.assertEqual(conn.execute("SELECT seq FROM sqlite_sequence WHERE name='evaluation_assignments'").fetchone()[0],80)
            conn.close()

    def test_legacy_new_forms_do_not_inherit_other_types_but_old_answers_are_kept(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/'old.db');self.legacy_fixture(path)
            conn=sqlite3.connect(path)
            conn.executescript('''ALTER TABLE evaluation_questions ADD COLUMN evaluation_type TEXT DEFAULT '동료사원 평가';
                INSERT INTO evaluation_questions(id,question_text,category,is_essay,evaluation_type)
                    VALUES (2,'Other type question','Other',0,'Other type');
                INSERT INTO evaluation_answers VALUES(12,9,2,4,'');''')
            conn.commit();conn.close()
            migrations.migrate(path)
            conn=sqlite3.connect(path);conn.row_factory=sqlite3.Row
            project_id=conn.execute('SELECT project_id FROM evaluation_assignments WHERE id=7').fetchone()[0]
            self.assertEqual([q['question_id'] for q in records.project_questions(conn,project_id)],[1])
            detail=records.evaluation_detail(conn,7)
            self.assertEqual({a['question_id'] for a in detail['answers']},{1,2})
            self.assertEqual(detail['total_score'],7)
            conn.close()

    def test_old_unique_project_constraint_custom_columns_and_index_are_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/'old.db');self.legacy_fixture(path)
            conn=sqlite3.connect(path)
            conn.executescript('''CREATE TABLE evaluation_projects(id INTEGER PRIMARY KEY AUTOINCREMENT,evaluatee_id INTEGER NOT NULL UNIQUE,
                title TEXT NOT NULL,external_reference TEXT,FOREIGN KEY(evaluatee_id) REFERENCES employees(id) ON DELETE CASCADE);
                INSERT INTO evaluation_projects VALUES(4,1,'Original title','Original reference');
                CREATE UNIQUE INDEX legacy_person_index ON evaluation_projects(evaluatee_id);
                CREATE INDEX custom_reference_index ON evaluation_projects(external_reference);''')
            conn.commit();conn.close()
            migrations.migrate(path)
            conn=sqlite3.connect(path);conn.row_factory=sqlite3.Row
            self.assertEqual(conn.execute('SELECT external_reference FROM evaluation_projects WHERE id=4').fetchone()[0],'Original reference')
            rid=conn.execute("INSERT INTO evaluation_rounds(name) VALUES ('Next')").lastrowid
            conn.execute("INSERT INTO evaluation_projects(evaluatee_id,title,round_id,evaluation_type) VALUES (1,'Next',?,'동료사원 평가')",(rid,))
            self.assertIsNotNone(conn.execute("SELECT name FROM sqlite_master WHERE name='custom_reference_index'").fetchone())
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(),[])
            conn.close()


@unittest.skipUnless(os.environ.get('EVALUATOR_TEST_BACKUP'), 'Set EVALUATOR_TEST_BACKUP for read-only backup rehearsal')
class ProvidedBackupTests(unittest.TestCase):
    def test_supplied_backup_records_and_history_survive(self):
        original=Path(os.environ['EVALUATOR_TEST_BACKUP']).resolve()
        original_hash=hashlib.sha256(original.read_bytes()).hexdigest()
        source=sqlite3.connect(original.as_uri()+'?mode=ro',uri=True)
        source.row_factory=sqlite3.Row
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/'copy.db');copy=sqlite3.connect(path)
            source.backup(copy);copy.close();source.close()
            migrations.migrate(path)
            conn=sqlite3.connect(path);conn.row_factory=sqlite3.Row
            ids=[r[0] for r in conn.execute('SELECT assignment_id FROM evaluations WHERE record_snapshot IS NOT NULL')]
            before=[hashlib.sha256(json.dumps(records.evaluation_detail(conn,i),sort_keys=True).encode()).hexdigest() for i in ids]
            df=records.export_results(conn)
            self.assertEqual(len(df),345)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM evaluations').fetchone()[0],249)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM evaluation_answers').fetchone()[0],2739)
            conn.execute("UPDATE employees SET name='Changed',team_name=NULL,position=NULL,phone=NULL")
            conn.execute("UPDATE evaluation_questions SET question_text='Changed',is_active=0,is_essay=1")
            conn.commit()
            after=[hashlib.sha256(json.dumps(records.evaluation_detail(conn,i),sort_keys=True).encode()).hexdigest() for i in ids]
            self.assertEqual(before,after)
            self.assertEqual(len(records.export_results(conn)),345)
            conn.close()
            self.assertFalse(migrations.migrate(path)['changed'])
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),original_hash)


if __name__=='__main__':
    unittest.main()
