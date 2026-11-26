const fileInput = document.querySelector('#fileInput');
const uploadCard = document.querySelector('#uploadCard');
const jobPanel = document.querySelector('#jobPanel');
const stemInfo = {
  vocals: { label: 'Vocals', note: 'The voice, front and center', color: 'violet', icon: '◖' },
  drums: { label: 'Drums', note: 'The pulse that moves it all', color: 'orange', icon: '▦' },
  bass: { label: 'Bass', note: 'The low end, loud and clear', color: 'blue', icon: '≋' },
  guitar: { label: 'Guitar', note: 'Guitar parts identified by the model', color: 'green', icon: '⌁' },
  piano: { label: 'Piano', note: 'Piano parts identified by the model', color: 'violet', icon: '▥' },
  other: { label: 'Other instruments', note: 'The model’s unclassified accompaniment', color: 'orange', icon: '✳' },
  instrumental: { label: 'Instrumental mix', note: 'Combined non-vocal stems', color: 'blue', icon: '♫' },
};
let pollTimer;

function chooseFile(file) {
  if (!file) return;
  if (!file.type.startsWith('audio/') && !/\.(mp3|wav|flac|m4a|ogg|aiff?)$/i.test(file.name)) {
    showError('That does not look like an audio file. Try an MP3, WAV, FLAC, M4A, OGG, or AIFF.');
    return;
  }
  if (file.size > 100 * 1024 * 1024) {
    showError('That file is over the 100 MB limit. Choose a smaller audio file.');
    return;
  }
  clearTimeout(pollTimer);
  uploadCard.classList.add('hidden');
  jobPanel.classList.remove('hidden');
  document.querySelector('#trackName').textContent = file.name;
  document.querySelector('#trackMeta').textContent = `${formatBytes(file.size)} · Preparing to separate`;
  document.querySelector('#progressBlock').classList.remove('hidden');
  document.querySelector('#stemsSection').classList.add('hidden');
  document.querySelector('#errorBox').classList.add('hidden');
  setProgress(3, 'Uploading your track…');
  upload(file);
}

async function upload(file) {
  const form = new FormData();
  form.append('file', file);
  try {
    const response = await fetch('/api/separate', { method: 'POST', body: form });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not start the separation.');
    document.querySelector('#trackMeta').textContent = `${formatBytes(file.size)} · Six-stem separation running`;
    setProgress(10, 'Finding the layers in your song…');
    poll(data.job_id);
  } catch (error) {
    showError(error.message || 'Could not connect to StemStudio. Is the local server running?');
  }
}

async function poll(jobId) {
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.detail || 'Could not check the separation status.');
    if (job.status === 'complete') {
      setProgress(100, 'Your stems are ready.');
      document.querySelector('#trackMeta').textContent = 'Separation complete · 7 tracks';
      document.querySelector('#progressBlock').classList.add('hidden');
      renderStems(job.stems);
      return;
    }
    if (job.status === 'error') throw new Error(job.error || 'Separation did not finish.');
    setProgress(job.progress || (job.status === 'queued' ? 8 : 20), job.status === 'queued' ? 'Waiting to start…' : 'Separating your track… This can take several minutes.');
    pollTimer = setTimeout(() => poll(jobId), 2500);
  } catch (error) {
    showError(error.message || 'Something went wrong while checking the job.');
  }
}

function renderStems(stems) {
  const list = document.querySelector('#stemList');
  list.replaceChildren();
  for (const [key, src] of Object.entries(stems)) {
    const details = stemInfo[key] || { label: key, note: 'Separated audio stem', color: 'violet', icon: '♫' };
    const row = document.createElement('article');
    row.className = `stem-row ${details.color}`;
    const icon = document.createElement('div');
    icon.className = 'stem-icon';
    icon.textContent = details.icon;
    const info = document.createElement('div');
    info.className = 'stem-info';
    const title = document.createElement('strong');
    title.textContent = details.label;
    const note = document.createElement('span');
    note.textContent = details.note;
    info.append(title, note);
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.preload = 'none';
    audio.src = src;
    audio.setAttribute('aria-label', `${details.label} audio player`);
    const download = document.createElement('a');
    download.className = 'download-button';
    download.href = src;
    download.download = `${key}.wav`;
    download.textContent = '↓';
    download.setAttribute('aria-label', `Download ${details.label}`);
    row.append(icon, info, audio, download);
    list.append(row);
  }
  document.querySelector('#stemsSection').classList.remove('hidden');
}

function setProgress(percent, message) {
  document.querySelector('#progressFill').style.width = `${percent}%`;
  document.querySelector('#progressPercent').textContent = `${percent}%`;
  document.querySelector('#progressText').textContent = message;
}
function showError(message) {
  const box = document.querySelector('#errorBox');
  box.textContent = message;
  box.classList.remove('hidden');
  document.querySelector('#progressBlock').classList.add('hidden');
}
function formatBytes(bytes) {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
function reset() {
  clearTimeout(pollTimer);
  jobPanel.classList.add('hidden');
  uploadCard.classList.remove('hidden');
  fileInput.value = '';
}

document.querySelector('#browseButton').addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (event) => chooseFile(event.target.files[0]));
document.querySelector('#removeButton').addEventListener('click', reset);
document.querySelector('#anotherButton').addEventListener('click', reset);
for (const eventName of ['dragenter', 'dragover']) {
  uploadCard.addEventListener(eventName, (event) => { event.preventDefault(); uploadCard.classList.add('dragging'); });
}
for (const eventName of ['dragleave', 'drop']) {
  uploadCard.addEventListener(eventName, (event) => { event.preventDefault(); uploadCard.classList.remove('dragging'); });
}
uploadCard.addEventListener('drop', (event) => chooseFile(event.dataTransfer.files[0]));
