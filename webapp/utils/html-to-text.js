/**
 * Reddit stores post/comment bodies as HTML (selftext_html, body_html).
 * Use plain-text fields (selftext, body) when present; otherwise decode and strip HTML here.
 */

/**
 * Decode HTML entities in a string (e.g. &lt; → <, &amp; → &).
 * @param {string} str
 * @returns {string}
 */
function decodeHtmlEntities(str) {
  if (str == null || typeof str !== 'string') return '';
  const textarea = typeof document !== 'undefined'
    ? document.createElement('textarea')
    : null;
  if (textarea) {
    textarea.innerHTML = str;
    return textarea.value;
  }
  return str
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(parseInt(n, 10)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, n) => String.fromCharCode(parseInt(n, 16)));
}

/**
 * Strip HTML tags and return plain text. Decodes entities first.
 * Safe for display (no script execution). Use for post/comment bodies from Reddit.
 * @param {string} htmlString - Raw HTML (e.g. from selftext_html or body_html)
 * @returns {string} Plain text safe to show
 */
function htmlToPlainText(htmlString) {
  if (htmlString == null || typeof htmlString !== 'string') return '';
  const decoded = decodeHtmlEntities(htmlString);
  if (typeof document !== 'undefined' && typeof DOMParser !== 'undefined') {
    try {
      const doc = new DOMParser().parseFromString(decoded, 'text/html');
      return doc.body?.textContent ?? decoded;
    } catch {
      return decoded.replace(/<[^>]*>/g, '');
    }
  }
  return decoded.replace(/<[^>]*>/g, '');
}

/**
 * Optionally sanitize HTML for rich display (e.g. with DOMPurify).
 * For now returns decoded string; integrate DOMPurify in the app if you need safe innerHTML.
 * @param {string} htmlString
 * @returns {string}
 */
function sanitizeHtml(htmlString) {
  if (htmlString == null || typeof htmlString !== 'string') return '';
  return decodeHtmlEntities(htmlString);
}

export { decodeHtmlEntities, htmlToPlainText, sanitizeHtml };
