"""
FB AI Content Agent - Group Photo Compositor
Зураг upload → Composite prompt → Gemini зураг (1-3 хувилбар) → Татах
"""

import os
import uuid
import secrets
import logging
import asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, Request, Cookie
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from dotenv import load_dotenv
from typing import List, Optional

import image_gen
import ai_agent


load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

jobs: dict[str, dict] = {}
sessions: dict[str, str] = {}  # token -> role

USERS = {
    "admin": os.environ.get("ADMIN_PASSWORD", "admin123"),
    "ajiltan": os.environ.get("WORKER_PASSWORD", "ajiltan123"),
}

def get_user(request: Request) -> Optional[str]:
    token = request.cookies.get("session")
    return sessions.get(token) if token else None

app = FastAPI(title="FB AI Content Agent")


HTML = """<!DOCTYPE html>
<html lang="mn">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Group Photo AI</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #060609; color: #d4d4e0;
    height: 100vh; display: flex; flex-direction: column; overflow: hidden;
  }
  /* Top bar */
  .topbar {
    display: flex; align-items: center; gap: 12px;
    padding: 0 24px; height: 56px; 
    border-bottom: 1px solid rgba(255,255,255,0.05);
    background: rgba(14, 14, 20, 0.8);
    backdrop-filter: blur(12px);
    flex-shrink: 0;
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    z-index: 10;
  }
  .topbar-logo {
    font-size: 1.1rem; font-weight: 800;
    background: linear-gradient(135deg, #a78bfa, #3b82f6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    letter-spacing: 0.5px;
  }
  .topbar-sep { width: 1px; height: 18px; background: rgba(255,255,255,0.1); }
  .topbar-tab {
    padding: 6px 14px; border-radius: 8px; font-size: 0.85rem; font-weight: 500;
    color: #8b8b9a; cursor: pointer; border: none; background: transparent;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .topbar-tab:hover { color: #fff; background: rgba(255,255,255,0.05); }
  .topbar-tab.active { background: #1e1e2e; color: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }

  /* Layout */
  .layout { display: flex; flex: 1; overflow: hidden; background: radial-gradient(circle at top center, #110e1c 0%, #060609 100%); }

  /* Sidebar */
  .sidebar {
    width: 340px; flex-shrink: 0;
    background: rgba(10, 10, 15, 0.6);
    backdrop-filter: blur(8px);
    border-right: 1px solid rgba(255,255,255,0.05);
    display: flex; flex-direction: column; overflow: hidden;
    box-shadow: 4px 0 24px rgba(0,0,0,0.15);
  }
  .sidebar-scroll { flex: 1; overflow-y: auto; padding: 16px; }
  .sidebar-scroll::-webkit-scrollbar { width: 4px; }
  .sidebar-scroll::-webkit-scrollbar-track { background: transparent; }
  .sidebar-scroll::-webkit-scrollbar-thumb { background: #2a2a38; border-radius: 4px; }

  .sidebar-footer {
    padding: 12px 16px; border-top: 1px solid #1e1e28; flex-shrink: 0;
  }

  .sec-label {
    font-size: 0.75rem; color: #6e6e8a; font-weight: 700;
    letter-spacing: 0.12em; margin-bottom: 12px; margin-top: 24px;
    display: flex; align-items: center; gap: 8px;
  }
  .sec-label::after { content:""; flex:1; height:1px; background: rgba(255,255,255,0.05); }
  .sec-label:first-child { margin-top: 0; }

  /* Upload */
  .upload-area {
    border: 1.5px dashed rgba(124, 58, 237, 0.3); border-radius: 14px;
    padding: 24px 16px; text-align: center; cursor: pointer;
    background: linear-gradient(180deg, rgba(20, 16, 42, 0.4) 0%, rgba(18, 18, 28, 0.6) 100%);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative; overflow: hidden;
  }
  .upload-area::before {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(circle at center, rgba(124,58,237,0.1) 0%, transparent 70%);
    opacity: 0; transition: opacity 0.3s;
  }
  .upload-area:hover::before, .upload-area.dragover::before { opacity: 1; }
  .upload-area:hover, .upload-area.dragover { 
    border-color: #8b5cf6; 
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(124, 58, 237, 0.15);
  }
  .upload-area input[type=file] { position: absolute; inset: 0; opacity: 0; cursor: pointer; z-index: 2; }
  .upload-icon { font-size: 1.8rem; margin-bottom: 8px; position: relative; z-index: 1; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.3)); }
  .upload-hint { color: #8b8b9a; font-size: 0.82rem; line-height: 1.6; position: relative; z-index: 1; }
  .upload-hint strong { color: #a78bfa; font-weight: 600; }

  /* Preview */
  .preview-grid {
    display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;
  }
  .preview-item {
    position: relative; border-radius: 12px; overflow: hidden;
    width: 64px; height: 64px; background: #12121c; 
    border: 2px solid #2a2a3e; flex-shrink: 0;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    transition: transform 0.2s, border-color 0.2s;
  }
  .preview-item:hover { transform: scale(1.05); border-color: #7c3aed; }
  .preview-item img { width: 100%; height: 100%; object-fit: cover; }
  .preview-item .rm {
    position: absolute; top: 2px; right: 2px;
    background: rgba(0,0,0,0.8); color: #fff; border: none;
    border-radius: 50%; width: 16px; height: 16px; font-size: 9px;
    cursor: pointer; display: flex; align-items: center; justify-content: center;
  }

  /* Toggle buttons */
  .btn-group { display: flex; flex-wrap: wrap; gap: 8px; }
  .tog {
    padding: 6px 14px; border-radius: 8px; 
    border: 1px solid rgba(255,255,255,0.08);
    background: rgba(20,20,30,0.5); color: #8b8b9a; font-size: 0.8rem; font-weight: 500; cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    font-family: inherit;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  }
  .tog:hover { 
    border-color: rgba(124, 58, 237, 0.5); 
    color: #e0e0f0; 
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(124, 58, 237, 0.2);
  }
  .tog.active { 
    background: linear-gradient(135deg, rgba(88, 28, 135, 0.4) 0%, rgba(124, 58, 237, 0.2) 100%);
    border-color: #7c3aed; color: #fff; font-weight: 600; 
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.25), inset 0 1px 0 rgba(255,255,255,0.1);
  }

  /* Textarea */
  textarea {
    width: 100%; background: rgba(10,10,15,0.6); 
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px; color: #e0e0f0; font-size: 0.85rem;
    padding: 12px 14px; outline: none; font-family: inherit;
    transition: all 0.3s ease; resize: none; height: 80px;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);
  }
  textarea:focus { border-color: #8b5cf6; box-shadow: inset 0 2px 4px rgba(0,0,0,0.2), 0 0 0 3px rgba(124,58,237,0.15); }
  textarea::placeholder { color: #50506a; }

  /* Run button (3D Premium) */
  .run-btn {
    width: 100%; padding: 14px;
    background: linear-gradient(to bottom, #8b5cf6, #6d28d9);
    border: none; border-radius: 12px;
    color: white; font-size: 0.95rem; font-weight: 700; letter-spacing: 0.5px;
    cursor: pointer; font-family: inherit;
    display: flex; align-items: center; justify-content: center; gap: 8px;
    box-shadow: 0 4px 0 #4c1d95, 0 8px 20px rgba(109, 40, 217, 0.4);
    transition: all 0.1s active, all 0.2s hover;
    position: relative; overflow: hidden;
  }
  .run-btn::after {
    content: ''; position: absolute; inset: 0; background: linear-gradient(to right, transparent, rgba(255,255,255,0.2), transparent);
    transform: translateX(-100%);
  }
  .run-btn:hover { 
    background: linear-gradient(to bottom, #9366f9, #7c3aed);
    transform: translateY(-2px);
    box-shadow: 0 6px 0 #4c1d95, 0 12px 24px rgba(109, 40, 217, 0.5);
  }
  .run-btn:hover::after { transform: translateX(100%); transition: transform 0.6s ease; }
  .run-btn:active { 
    transform: translateY(4px); 
    box-shadow: 0 0 0 #4c1d95, 0 2px 8px rgba(109, 40, 217, 0.3);
  }
  .run-btn:disabled { 
    background: #2a1b42; color: #504070; cursor: not-allowed; 
    box-shadow: none; transform: none;
  }
  .run-count {
    background: rgba(255,255,255,0.15); border-radius: 4px;
    padding: 1px 8px; font-size: 0.8rem;
  }

  /* Main area */
  .main {
    flex: 1; overflow-y: auto; padding: 24px;
    display: flex; flex-direction: column;
  }
  .main::-webkit-scrollbar { width: 6px; }
  .main::-webkit-scrollbar-track { background: transparent; }
  .main::-webkit-scrollbar-thumb { background: #2a2a38; border-radius: 4px; }

  /* Empty state */
  .empty-state {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 12px;
    color: #30304a; text-align: center;
  }
  .empty-state .big-icon { font-size: 3.5rem; opacity: 0.4; }
  .empty-state p { font-size: 0.9rem; }

  /* Progress */
  .progress-box { display: none; margin-bottom: 24px; padding: 20px; background: rgba(14,14,20,0.8); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.3); }
  .progress-box.show { display: block; animation: slideIn 0.4s ease forwards; }
  @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
  .prog-header { font-size: 0.8rem; color: #8b8b9a; font-weight: 700; letter-spacing: 0.1em; margin-bottom: 16px; display:flex; align-items:center; gap:8px;}
  .prog-header::after { content:''; flex:1; height:1px; background:rgba(255,255,255,0.05); }
  .step { display: flex; align-items: center; gap: 14px; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.03); }
  .step:last-child { border-bottom: none; }
  .step-icon {
    width: 28px; height: 28px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; flex-shrink: 0;
    transition: all 0.3s ease; box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);
  }
  .step-icon.wait   { background: #1a1a24; border: 1px solid #2a2a38; color: #50506a; }
  .step-icon.active { background: linear-gradient(135deg, #4c1d95, #7c3aed); color: #fff; box-shadow: 0 0 15px rgba(124,58,237,0.5); animation: pulse 1.5s infinite; border: 1px solid #9366f9; }
  .step-icon.done   { background: linear-gradient(135deg, #064e3b, #10b981); color: #fff; box-shadow: 0 0 15px rgba(16,185,129,0.3); border: 1px solid #34d399; }
  @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(124,58,237,0.4); } 70% { box-shadow: 0 0 0 10px rgba(124,58,237,0); } 100% { box-shadow: 0 0 0 0 rgba(124,58,237,0); } }
  .step-text { font-size: 0.9rem; color: #70708a; font-weight: 500; }
  .step-text.active { color: #fff; font-weight: 600; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }

  /* Results */
  .results-header {
    font-size: 0.8rem; color: #8b8b9a; font-weight: 700;
    letter-spacing: 0.12em; margin-bottom: 20px; display:flex; align-items:center; gap:10px;
  }
  .results-header::after { content:''; flex:1; height:1px; background:rgba(255,255,255,0.05); }
  .results-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 24px;
  }
  .result-card {
    background: #111118; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; overflow: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
  }
  .result-card:hover { 
    border-color: rgba(124,58,237,0.5); 
    transform: translateY(-4px);
    box-shadow: 0 20px 40px rgba(0,0,0,0.4), 0 0 20px rgba(124,58,237,0.1);
  }
  .result-card img {
    width: 100%; display: block; cursor: zoom-in;
    transition: opacity 0.3s;
  }
  .result-card img:hover { opacity: 0.9; }
  .result-card-footer {
    padding: 16px; display: flex; align-items: center; justify-content: space-between;
    background: linear-gradient(to bottom, #111118, #0a0a0f);
    border-top: 1px solid rgba(255,255,255,0.05);
  }
  .result-num { font-size: 0.75rem; color: #8b8b9a; font-weight: 700; letter-spacing: 0.05em; }
  .dl-btn {
    padding: 8px 16px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
    color: #e0e0f0; text-decoration: none; border-radius: 8px;
    font-size: 0.8rem; font-weight: 600; transition: all 0.2s;
    display: flex; align-items: center; gap: 6px;
  }
  .dl-btn:hover { background: #e0e0f0; color: #000; border-color: #e0e0f0; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(255,255,255,0.15); }

  /* Error */
  .error-box {
    display: none; margin-bottom: 16px; background: #1e0a0a;
    border: 1px solid #5a1a1a; border-radius: 8px;
    padding: 10px 14px; color: #f87171; font-size: 0.82rem; word-break: break-word;
  }
  .error-box.show { display: block; }

  /* Lightbox */
  .lightbox {
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.92);
    z-index: 1000; align-items: center; justify-content: center; cursor: pointer;
  }
  .lightbox.show { display: flex; }
  .lightbox img { max-width: 90vw; max-height: 90vh; border-radius: 10px; }
</style>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
</head>
<body>

<div class="topbar">
  <span class="topbar-logo">✨ Degjin Ai Studio</span>
  <div class="topbar-sep"></div>
  <button class="topbar-tab active" id="tab-group" onclick="switchTab('group')">📸 Зураг үүсгэх</button>
  <button class="topbar-tab" id="tab-restore" onclick="switchTab('restore')">🎨 Зураг сэргээх</button>
  <div style="flex:1"></div>
  <a href="/logout" style="padding:6px 14px;border-radius:8px;font-size:0.82rem;color:#6e6e8a;text-decoration:none;border:1px solid rgba(255,255,255,0.07);transition:all 0.2s;" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='#6e6e8a'">Гарах ↗</a>
</div>

<div class="layout">
  <!-- Sidebar -->
  <div class="sidebar">
    <div class="sidebar-scroll">

      <!-- GROUP PHOTO PANEL -->
      <div id="groupPanel">
      <div class="sec-label">INPUT IMAGES</div>
      <div class="upload-area" id="uploadArea">
        <input type="file" id="fileInput" accept="image/*" multiple onchange="handleFiles(this.files)">
        <div class="upload-icon">🖼</div>
        <div class="upload-hint">Зургуудаа чирж тавих эсвэл<br><strong>дарж сонгох</strong> · JPG · PNG</div>
      </div>
      <div id="previewGrid" class="preview-grid"></div>

      <div class="sec-label">ХУВИЛБАРЫН ТОО</div>
      <div class="btn-group" id="variantsGroup">
        <button class="tog active" onclick="pick('variants',this,1)">1x</button>
        <button class="tog" onclick="pick('variants',this,2)">2x</button>
        <button class="tog" onclick="pick('variants',this,3)">3x</button>
      </div>

      <div class="sec-label">ХҮНИЙ ТОО</div>
      <div class="btn-group" id="countGroup">
        <button class="tog" onclick="pick('count',this,'1 person')">1</button>
        <button class="tog" onclick="pick('count',this,'2 people')">2</button>
        <button class="tog" onclick="pick('count',this,'3 people')">3</button>
        <button class="tog active" onclick="pick('count',this,'4 people')">4</button>
        <button class="tog" onclick="pick('count',this,'5 people')">5</button>
        <button class="tog" onclick="pick('count',this,'6 people')">6</button>
        <button class="tog" onclick="pick('count',this,'7 people')">7</button>
        <button class="tog" onclick="pick('count',this,'8 people')">8</button>
        <button class="tog" onclick="pick('count',this,'9 people')">9</button>
        <button class="tog" onclick="pick('count',this,'10 people')">10</button>
      </div>

      <div class="sec-label">ХУВЦАС</div>
      <div class="btn-group" id="clothingGroup">
        <button class="tog active" onclick="pick('clothing',this,'casual')">👕 Casual</button>
        <button class="tog" onclick="pick('clothing',this,'formal')">👔 Formal</button>
        <button class="tog" onclick="pick('clothing',this,'Mongolian deel')">🥻 Дээл</button>
        <button class="tog" onclick="pick('clothing',this,'own clothing')">📸 Өөрийн</button>
      </div>

      <div class="sec-label">ДЭВСГЭР</div>
      <div class="btn-group" id="bgGroup">
        <button class="tog active" onclick="pick('bg',this,'Mongolian nature')">🏔 Байгаль</button>
        <button class="tog" onclick="pick('bg',this,'studio')">🎨 Studio</button>
        <button class="tog" onclick="pick('bg',this,'Mongolian ger')">🏠 Гэр</button>
      </div>

      <div class="sec-label">ХЭМЖЭЭ / ЧИГЛЭЛ</div>
      <div class="btn-group" id="formatGroup">
        <button class="tog active" onclick="pick('format',this,'A4 landscape')">A4 Landscape</button>
        <button class="tog" onclick="pick('format',this,'A4 portrait')">A4 Portrait</button>
        <button class="tog" onclick="pick('format',this,'A3 landscape')">A3 Landscape</button>
        <button class="tog" onclick="pick('format',this,'A3 portrait')">A3 Portrait</button>
      </div>

      <div class="sec-label">НЭМЭЛТ ТАЙЛБАР</div>
      <textarea id="extraDesc" placeholder="Жнь: 2 эмэгтэй, 1 эрэгтэй..."></textarea>

      </div><!-- /groupPanel -->

      <!-- RESTORE PANEL -->
      <div id="restorePanel" style="display:none">
      <div class="sec-label">ХУУЧИН ЗУРАГ ОРУУЛАХ</div>
      <div class="upload-area" id="uploadAreaRestore">
        <input type="file" id="fileInputRestore" accept="image/*" onchange="handleFilesRestore(this.files)">
        <div class="upload-icon">🖼</div>
        <div class="upload-hint">Хуучин зургаа чирж тавих эсвэл<br><strong>дарж сонгох</strong> · JPG · PNG</div>
      </div>
      <div id="previewGridRestore" class="preview-grid"></div>

      <div class="sec-label">ТАЙЛБАР</div>
      <textarea id="restoreDesc" placeholder="Жнь: colorize this old photo, restore scratches..."></textarea>
      </div><!-- /restorePanel -->

    </div>
    <div class="sidebar-footer">
      <button class="run-btn" id="genBtn" onclick="generate()">
        <span>▶ Run</span>
        <span class="run-count" id="runCount">1x</span>
      </button>
    </div>
  </div>

  <!-- Main content -->
  <div class="main" id="mainArea">
    <div class="empty-state" id="emptyState">
      <div class="big-icon">🖼</div>
      <p>Зүүн талд тохиргоо хийгээд<br><strong style="color:#5050a0">Run</strong> дарна уу</p>
    </div>

    <div class="progress-box" id="progressBox">
      <div class="prog-header">PROCESSING</div>
      <div class="step">
        <div class="step-icon wait" id="s1i">1</div>
        <div class="step-text" id="s1t">Composition prompt үүсгэж байна...</div>
      </div>
      <div class="step">
        <div class="step-icon wait" id="s2i">2</div>
        <div class="step-text" id="s2t">AI зураг үүсгэж байна...</div>
      </div>
    </div>

    <div class="error-box" id="errorBox"></div>

    <div id="resultsSection" style="display:none">
      <div class="results-header">ҮҮСГЭСЭН ЗУРГУУД</div>
      <div class="results-grid" id="resultsGrid"></div>
    </div>
  </div>
</div>

<!-- Lightbox -->
<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <img id="lightboxImg" src="">
</div>

<script>
let selectedFiles = [];
let selectedFilesRestore = [];
let picks = { variants: 1, count: '4 people', clothing: 'casual', bg: 'Mongolian nature', format: 'A4 landscape' };
let pollInterval = null;
let currentTab = 'group';

function switchTab(tab) {
  currentTab = tab;
  document.getElementById('tab-group').classList.toggle('active', tab === 'group');
  document.getElementById('tab-restore').classList.toggle('active', tab === 'restore');
  document.getElementById('groupPanel').style.display = tab === 'group' ? '' : 'none';
  document.getElementById('restorePanel').style.display = tab === 'restore' ? '' : 'none';
  document.getElementById('runCount').style.display = tab === 'group' ? '' : 'none';
}

function pick(group, btn, val) {
  picks[group] = val;
  document.querySelectorAll(`#${group}Group .tog`).forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  if (group === 'variants') document.getElementById('runCount').textContent = val + 'x';
}

const area = document.getElementById('uploadArea');
area.addEventListener('dragover', e => { e.preventDefault(); area.classList.add('dragover'); });
area.addEventListener('dragleave', () => area.classList.remove('dragover'));
area.addEventListener('drop', e => { e.preventDefault(); area.classList.remove('dragover'); handleFiles(e.dataTransfer.files); });

function handleFiles(files) {
  for (const f of files) if (f.type.startsWith('image/')) selectedFiles.push(f);
  renderPreviews();
}
function renderPreviews() {
  const grid = document.getElementById('previewGrid');
  grid.innerHTML = '';
  selectedFiles.forEach((f, i) => {
    const url = URL.createObjectURL(f);
    const div = document.createElement('div');
    div.className = 'preview-item';
    div.innerHTML = `<img src="${url}"><button class="rm" onclick="removeFile(${i})">✕</button>`;
    grid.appendChild(div);
  });
}
function removeFile(i) { selectedFiles.splice(i, 1); renderPreviews(); }

const areaR = document.getElementById('uploadAreaRestore');
areaR.addEventListener('dragover', e => { e.preventDefault(); areaR.classList.add('dragover'); });
areaR.addEventListener('dragleave', () => areaR.classList.remove('dragover'));
areaR.addEventListener('drop', e => { e.preventDefault(); areaR.classList.remove('dragover'); handleFilesRestore(e.dataTransfer.files); });

function handleFilesRestore(files) {
  selectedFilesRestore = [];
  for (const f of files) if (f.type.startsWith('image/')) selectedFilesRestore.push(f);
  renderPreviewsRestore();
}
function renderPreviewsRestore() {
  const grid = document.getElementById('previewGridRestore');
  grid.innerHTML = '';
  selectedFilesRestore.forEach((f, i) => {
    const url = URL.createObjectURL(f);
    const div = document.createElement('div');
    div.className = 'preview-item';
    div.innerHTML = `<img src="${url}"><button class="rm" onclick="removeFileRestore(${i})">✕</button>`;
    grid.appendChild(div);
  });
}
function removeFileRestore(i) { selectedFilesRestore.splice(i, 1); renderPreviewsRestore(); }

async function generate() {
  document.getElementById('genBtn').disabled = true;
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('progressBox').classList.add('show');
  document.getElementById('resultsSection').style.display = 'none';
  document.getElementById('errorBox').classList.remove('show');
  document.getElementById('resultsGrid').innerHTML = '';
  setStep(1,'active'); setStep(2,'wait');

  let resp;
  if (currentTab === 'restore') {
    if (!selectedFilesRestore.length) {
      alert('Зураг upload хийнэ үү!');
      document.getElementById('genBtn').disabled = false;
      document.getElementById('progressBox').classList.remove('show');
      return;
    }
    const form = new FormData();
    selectedFilesRestore.forEach(f => form.append('images', f));
    form.append('description', document.getElementById('restoreDesc').value);
    resp = await fetch('/restore', { method: 'POST', body: form });
  } else {
    if (!selectedFiles.length) {
      alert('Хамгийн багадаа 1 зураг upload хийнэ үү!');
      document.getElementById('genBtn').disabled = false;
      document.getElementById('progressBox').classList.remove('show');
      return;
    }
    const desc = `${picks.count}, ${picks.clothing} clothing, ${picks.bg} background, ${picks.format} format. ${document.getElementById('extraDesc').value}`.trim();
    const form = new FormData();
    selectedFiles.forEach(f => form.append('images', f));
    form.append('description', desc);
    form.append('variants', picks.variants);
    resp = await fetch('/generate', { method: 'POST', body: form });
  }
  const { job_id } = await resp.json();
  pollInterval = setInterval(() => pollStatus(job_id), 2000);
}

async function pollStatus(jobId) {
  const d = await (await fetch(`/status/${jobId}`)).json();
  if (d.step >= 1) setStep(1, d.step > 1 ? 'done' : 'active');
  if (d.step >= 2) setStep(2, d.step > 2 ? 'done' : 'active');
  if (d.status === 'done') {
    clearInterval(pollInterval);
    setStep(1,'done'); setStep(2,'done');
    showResults(jobId, d.count);
  } else if (d.status === 'error') {
    clearInterval(pollInterval);
    document.getElementById('errorBox').textContent = d.message || 'Алдаа гарлаа.';
    document.getElementById('errorBox').classList.add('show');
    document.getElementById('genBtn').disabled = false;
  }
}

function showResults(jobId, count) {
  document.getElementById('progressBox').classList.remove('show');
  const grid = document.getElementById('resultsGrid');
  grid.innerHTML = '';
  for (let i = 0; i < count; i++) {
    const url = `/download-image/${jobId}/${i}`;
    const card = document.createElement('div');
    card.className = 'result-card';
    card.innerHTML = `
      <img src="${url}" onclick="openLightbox('${url}')">
      <div class="result-card-footer">
        <span class="result-num">ХУВИЛБАР ${i + 1}</span>
        <a class="dl-btn" href="${url}" download="group_${jobId}_${i+1}.png">↓ Татах</a>
      </div>
    `;
    grid.appendChild(card);
  }
  document.getElementById('resultsSection').style.display = 'block';
  document.getElementById('genBtn').disabled = false;
}

function openLightbox(src) {
  document.getElementById('lightboxImg').src = src;
  document.getElementById('lightbox').classList.add('show');
}
function closeLightbox() { document.getElementById('lightbox').classList.remove('show'); }

function setStep(n, state) {
  const el_i = document.getElementById(`s${n}i`);
  const el_t = document.getElementById(`s${n}t`);
  if (!el_i) return;
  el_i.className = `step-icon ${state}`;
  el_t.className = `step-text ${state === 'active' ? 'active' : ''}`;
  el_i.textContent = state === 'done' ? '✓' : n;
}
</script>
</body>
</html>"""


LOGIN_HTML = """<!DOCTYPE html>
<html lang="mn">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Нэвтрэх · Degjin Ai Studio</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Inter', sans-serif;
    background: #060609;
    color: #d4d4e0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: radial-gradient(circle at top center, #110e1c 0%, #060609 100%);
  }
  .card {
    background: rgba(14,14,20,0.9);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 20px;
    padding: 40px 36px;
    width: 360px;
    box-shadow: 0 24px 60px rgba(0,0,0,0.5);
  }
  .logo {
    font-size: 1.3rem; font-weight: 800;
    background: linear-gradient(135deg, #a78bfa, #3b82f6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    text-align: center; margin-bottom: 8px;
  }
  .subtitle { text-align: center; color: #50506a; font-size: 0.82rem; margin-bottom: 32px; }
  .field { margin-bottom: 16px; }
  label { display: block; font-size: 0.78rem; color: #6e6e8a; font-weight: 600; letter-spacing: 0.08em; margin-bottom: 6px; }
  input {
    width: 100%; background: rgba(10,10,15,0.6);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px; color: #e0e0f0; font-size: 0.9rem;
    padding: 11px 14px; outline: none; font-family: inherit;
    transition: border-color 0.2s;
  }
  input:focus { border-color: #8b5cf6; }
  .btn {
    width: 100%; padding: 13px;
    background: linear-gradient(to bottom, #8b5cf6, #6d28d9);
    border: none; border-radius: 12px;
    color: white; font-size: 0.95rem; font-weight: 700;
    cursor: pointer; font-family: inherit; margin-top: 8px;
    box-shadow: 0 4px 0 #4c1d95, 0 8px 20px rgba(109,40,217,0.4);
    transition: all 0.1s;
  }
  .btn:hover { transform: translateY(-2px); box-shadow: 0 6px 0 #4c1d95, 0 12px 24px rgba(109,40,217,0.5); }
  .btn:active { transform: translateY(4px); box-shadow: none; }
  .err { background: #1e0a0a; border: 1px solid #5a1a1a; border-radius: 8px; padding: 10px 14px; color: #f87171; font-size: 0.82rem; margin-bottom: 16px; display: none; }
  .err.show { display: block; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">✨ Degjin Ai Studio</div>
  <div class="subtitle">Системд нэвтрэх</div>
  <div class="err" id="err">Нэвтрэх нэр эсвэл нууц үг буруу байна.</div>
  <form method="POST" action="/login">
    <div class="field">
      <label>ХЭРЭГЛЭГЧ</label>
      <input type="text" name="username" placeholder="admin / ajiltan" required autofocus>
    </div>
    <div class="field">
      <label>НУУЦ ҮГ</label>
      <input type="password" name="password" placeholder="••••••••" required>
    </div>
    <button class="btn" type="submit">Нэвтрэх →</button>
  </form>
</div>
<script>
  const p = new URLSearchParams(window.location.search);
  if (p.get('err')) document.getElementById('err').classList.add('show');
</script>
</body>
</html>"""


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return LOGIN_HTML


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if USERS.get(username) == password:
        token = secrets.token_hex(32)
        sessions[token] = username
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("session", token, httponly=True, max_age=86400 * 7)
        return resp
    return RedirectResponse("/login?err=1", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session")
    if token:
        sessions.pop(token, None)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session")
    return resp


@app.get("/", response_class=HTMLResponse)
async def ui(request: Request):
    if not get_user(request):
        return RedirectResponse("/login", status_code=303)
    return HTML


@app.post("/generate")
async def start_generate(
    request: Request,
    images: List[UploadFile] = File(...),
    description: str = Form(""),
    variants: int = Form(1),
):
    if not get_user(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    job_id = uuid.uuid4().hex[:10]
    image_bytes_list = [await img.read() for img in images]
    variants = max(1, min(3, variants))  # 1-3 хооронд
    jobs[job_id] = {"status": "processing", "step": 0, "message": "", "count": 0}
    asyncio.create_task(run_pipeline(job_id, image_bytes_list, description, variants))
    return {"job_id": job_id}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    return jobs.get(job_id) or JSONResponse({"status": "not_found"}, status_code=404)


@app.get("/download-image/{job_id}/{index}")
async def download_image(job_id: str, index: int):
    path = TEMP_DIR / f"{job_id}_{index}.png"
    if not path.exists():
        return JSONResponse({"error": "Зураг олдсонгүй"}, status_code=404)
    return FileResponse(str(path), media_type="image/png", filename=f"group_{job_id}_{index+1}.png")


@app.post("/restore")
async def start_restore(
    request: Request,
    images: List[UploadFile] = File(...),
    description: str = Form(""),
):
    if not get_user(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    job_id = uuid.uuid4().hex[:10]
    image_bytes_list = [await img.read() for img in images]
    jobs[job_id] = {"status": "processing", "step": 0, "message": "", "count": 0}
    asyncio.create_task(run_restore_pipeline(job_id, image_bytes_list, description))
    return {"job_id": job_id}


async def run_restore_pipeline(job_id: str, image_bytes_list: list[bytes], description: str):
    def update(step, status="processing", message="", count=0):
        jobs[job_id] = {"status": status, "step": step, "message": message, "count": count}

    try:
        update(1)
        prompt = await asyncio.to_thread(
            ai_agent.generate_restoration_prompt, description, image_bytes_list
        )
        logger.info(f"[{job_id}] Restore prompt бэлэн...")

        update(2)
        path = str(TEMP_DIR / f"{job_id}_0.png")
        result = await asyncio.to_thread(image_gen.generate_image, prompt, path, image_bytes_list)
        if result is not True:
            raise RuntimeError(str(result))

        update(3, status="done", count=1)
        logger.info(f"[{job_id}] Зураг сэргээлт амжилттай ✓")

    except Exception as e:
        logger.error(f"[{job_id}] Алдаа: {e}", exc_info=True)
        update(0, status="error", message=str(e))


async def run_pipeline(job_id: str, image_bytes_list: list[bytes],
                        description: str, variants: int):
    def update(step, status="processing", message="", count=0):
        jobs[job_id] = {"status": status, "step": step, "message": message, "count": count}

    try:
        # Алхам 1: Composition prompt үүсгэх
        update(1)
        prompt = await asyncio.to_thread(
            ai_agent.generate_composition_prompt, description, image_bytes_list
        )
        logger.info(f"[{job_id}] Prompt бэлэн, {variants} хувилбар үүсгэнэ...")

        # Алхам 2: N зураг зэрэг үүсгэх
        update(2)
        image_paths = [str(TEMP_DIR / f"{job_id}_{i}.png") for i in range(variants)]

        tasks = [
            asyncio.to_thread(image_gen.generate_image, prompt, path, image_bytes_list)
            for path in image_paths
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        if success_count == 0:
            raise RuntimeError(f"Жодон ч зураг үүсгэгдсэнгүй: {results[0]}")

        update(3, status="done", count=success_count)
        logger.info(f"[{job_id}] {success_count}/{variants} зураг амжилттай ✓")

    except Exception as e:
        logger.error(f"[{job_id}] Алдаа: {e}", exc_info=True)
        update(0, status="error", message=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 6060))
    logger.info(f"Сервер → http://localhost:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
