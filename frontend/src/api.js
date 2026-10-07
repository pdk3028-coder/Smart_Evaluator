// Reject cached pre-upgrade forms at the server before they change records.
export function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers);
  headers.set('X-App-Version', '2');
  return fetch(url, { ...options, headers });
}

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character]));
}

export function safePngDataUrl(value) {
  return typeof value === 'string' && value.length <= 750000 &&
    /^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(value) ? value : '';
}
