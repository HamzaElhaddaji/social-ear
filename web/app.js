const byId = id => document.getElementById(id);
const element = (tag, text, className) => { const node = document.createElement(tag); node.textContent = text; if (className) node.className = className; return node; };
let requestId = 0;
function params() { return new URLSearchParams({q: byId('search').value, sentiment: byId('sentiment').value}); }
async function load() {
  const id = ++requestId;
  try {
    const response = await fetch('/api/posts?' + params());
    if (!response.ok) throw new Error('Could not load conversations.');
    const {posts, summary} = await response.json();
    if (id !== requestId) return;
    byId('total').textContent = summary.total;
    byId('mix').replaceChildren();
    for (const label of ['positive', 'neutral', 'negative']) {
      byId(label).textContent = summary.sentiment[label];
      const row = element('div', '', 'mix-row');
      row.append(element('span', label), element('strong', summary.sentiment[label]));
      const meter = document.createElement('progress'); meter.max = summary.total || 1; meter.value = summary.sentiment[label]; meter.setAttribute('aria-label', label); row.append(meter); byId('mix').append(row);
    }
    byId('topics').replaceChildren(...summary.topics.map(topic => element('span', `${topic.name} · ${topic.count}`, 'topic')));
    if (!summary.topics.length) byId('topics').append(element('p', 'Import conversations to discover recurring words.', 'muted'));
    byId('posts').replaceChildren();
    for (const post of posts) {
      const card = element('article', '', 'post');
      const meta = element('div', '', 'post-meta'); meta.append(element('strong', post.source), element('span', post.published_at || 'No date supplied'), element('span', post.sentiment, 'badge ' + post.sentiment));
      card.append(meta, element('p', post.text)); byId('posts').append(card);
    }
    if (!posts.length) byId('posts').append(element('div', 'No conversations found. Import a CSV below or adjust your filters.', 'empty'));
    byId('export').href = '/api/export?' + params();
  } catch (error) { byId('message').textContent = error.message; }
}
byId('filters').addEventListener('submit', event => {event.preventDefault(); load();});
byId('sentiment').addEventListener('change', load);
byId('upload').addEventListener('submit', async event => {
  event.preventDefault(); const file = byId('file').files[0]; if (!file) return;
  if (file.size > 2 * 1024 * 1024) { byId('message').textContent = 'Choose a CSV smaller than 2 MB.'; return; }
  const button = event.currentTarget.querySelector('button'); button.disabled = true; byId('message').textContent = 'Importing…';
  try {
    const response = await fetch('/api/import', {method: 'POST', headers: {'Content-Type': 'text/csv'}, body: await file.text()});
    const result = await response.json(); if (!response.ok) throw new Error(result.error);
    byId('message').textContent = `Imported ${result.imported} conversations. Skipped ${result.duplicates} duplicates and ${result.empty} empty rows.`; await load();
  } catch (error) { byId('message').textContent = error.message; } finally { button.disabled = false; }
});
load();
