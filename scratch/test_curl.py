import urllib.request
with open("test_result_final.txt", "w", encoding="utf-8") as f:
    try:
        with urllib.request.urlopen("http://smartevaluator.pythonanywhere.com") as response:
            f.write(f"Status Code: {response.status}\n")
            f.write(f"Headers: {response.info()}\n")
    except Exception as e:
        f.write(f"Error: {e}\n")
