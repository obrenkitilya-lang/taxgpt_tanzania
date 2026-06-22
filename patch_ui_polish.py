FILE = '/workspaces/taxgpt_tanzania/frontend/index_fixed.html'

NEW_CSS = """*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',system-ui,-apple-system,sans-serif}
body{background:#020817;color:white;height:100vh;display:flex;font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}
.sidebar{width:268px;background:#070f26;border-right:1px solid #161f3a;display:flex;flex-direction:column;height:100vh;flex-shrink:0}
.sidebar-header{padding:22px 20px 18px;border-bottom:1px solid #161f3a}
.logo{font-size:22px;font-weight:700;letter-spacing:-0.5px;margin-bottom:14px;color:#fff}
.new-chat{width:100%;background:#dfff00;border:none;padding:11px 14px;border-radius:10px;font-weight:700;cursor:pointer;color:#0a0f00;font-size:14px;display:flex;align-items:center;justify-content:center;gap:8px;transition:background 0.15s,transform 0.1s;letter-spacing:0.1px}
.new-chat:hover{background:#c8e600}
.new-chat:active{transform:scale(0.98)}
.auth-section{padding:14px 16px;border-bottom:1px solid #161f3a}
.auth-btn{width:100%;padding:9px 14px;background:transparent;border:1px solid #dfff00;color:#dfff00;border-radius:8px;font-weight:600;cursor:pointer;font-size:13px;margin-bottom:7px;text-align:center;text-decoration:none;display:block;transition:background 0.15s,color 0.15s;letter-spacing:0.1px}
.auth-btn:hover{background:#dfff00;color:#0a0f00}
.auth-btn-primary{background:#dfff00;color:#0a0f00;border:none}
.auth-btn-primary:hover{background:#c8e600}
.user-info{padding:10px 12px;background:#0c1635;border-radius:10px;margin-bottom:10px;border:1px solid #161f3a}
.user-email{color:#e2e8f0;font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.user-badge{font-size:11px;color:#64748b;margin-top:3px;font-weight:500}
.admin-badge{background:#dfff00;color:#1e293b;font-size:10px;padding:2px 8px;border-radius:4px;font-weight:700;margin-left:6px}
.tools-section{padding:14px 16px;border-bottom:1px solid #161f3a}
.tools-title{font-size:10px;color:#475569;text-transform:uppercase;letter-spacing:1.2px;font-weight:600;margin-bottom:6px;padding:0 6px}
.tool-item{padding:9px 12px;border-radius:8px;cursor:pointer;font-size:14px;display:flex;align-items:center;gap:10px;color:#94a3b8;text-decoration:none;font-weight:500;transition:background 0.15s,color 0.15s;margin-bottom:1px}
.tool-item:hover{background:#111c44;color:#e2e8f0}
.tool-item.active{background:#111c44;color:#dfff00;font-weight:600}
.history-section{flex:1;display:flex;flex-direction:column;overflow:hidden}
.history-header{padding:14px 20px 8px;display:flex;justify-content:space-between;align-items:center}
.history-title-text{font-size:10px;color:#475569;text-transform:uppercase;letter-spacing:1.2px;font-weight:600}
.chat-history{flex:1;overflow-y:auto;padding:0 10px 12px;display:flex;flex-direction:column;gap:2px}
.history-item{padding:9px 12px;border-radius:8px;cursor:pointer;font-size:13px;display:flex;justify-content:space-between;align-items:center;gap:8px;color:#94a3b8;font-weight:500;transition:background 0.15s,color 0.15s}
.history-item:hover{background:#111c44;color:#e2e8f0}
.history-item.active{background:#1e3a5f;color:#e2e8f0}
.history-item-text{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.delete-btn{background:none;border:none;color:#64748b;cursor:pointer;font-size:14px;padding:0 4px;opacity:0;transition:opacity 0.15s}
.history-item:hover .delete-btn{opacity:1}
.delete-btn:hover{color:#ef4444}
.sidebar-footer{padding:12px 20px;border-top:1px solid #161f3a;font-size:11px;color:#475569;letter-spacing:0.2px;font-weight:500}
.main{flex:1;display:flex;flex-direction:column;height:100vh;overflow:hidden}
.limit-banner{background:#450a0a;border-bottom:1px solid #7f1d1d;color:#f87171;padding:10px 24px;text-align:center;font-size:13px;font-weight:500;flex-shrink:0}
.limit-banner a{color:#dfff00;text-decoration:underline;cursor:pointer}
.top-section{text-align:center;padding:32px 24px 16px;flex-shrink:0}
.top-section h1{font-size:38px;font-weight:800;margin-bottom:8px;letter-spacing:-1px;line-height:1.1}
.top-section p{color:#64748b;font-size:15px}
.tool-indicator{display:inline-flex;align-items:center;gap:6px;background:#0c1635;border:1px solid #1e293b;padding:6px 16px;border-radius:20px;font-size:12px;color:#94a3b8;margin-top:12px;font-weight:500;letter-spacing:0.2px}
.tool-indicator .dot{width:7px;height:7px;border-radius:50%;background:#dfff00;flex-shrink:0}
.chat-area{flex:1;overflow-y:auto;padding:24px 48px;display:flex;flex-direction:column;gap:20px}
.welcome-message{text-align:center;color:#475569;margin-top:80px}
.message{max-width:78%;padding:14px 20px;border-radius:14px;line-height:1.65;font-size:15px}
.user-message{align-self:flex-end;background:#1e3a5f;color:#e2e8f0;border-bottom-right-radius:4px}
.ai-message{align-self:flex-start;background:#0c1635;color:#e2e8f0;border:1px solid #161f3a;border-bottom-left-radius:4px}
.ai-message h1,.ai-message h2,.ai-message h3{margin:14px 0 8px;color:#dfff00;font-weight:700}
.ai-message p{margin:8px 0}
.ai-message ul,.ai-message ol{margin:10px 0 10px 22px}
.ai-message li{margin:5px 0}
.ai-message a{color:#dfff00;text-decoration:underline}
.ai-message strong{color:#dfff00;font-weight:700}
.ai-message code{background:#161f3a;padding:2px 7px;border-radius:5px;font-family:monospace;font-size:13px}
.ai-message pre{background:#161f3a;padding:14px;border-radius:10px;overflow-x:auto;margin:10px 0}
.ai-message pre code{background:none;padding:0}
.bottom-section{padding:16px 48px 28px;flex-shrink:0}
.search-box{width:100%;max-width:720px;min-height:56px;display:flex;background:#0c1635;border:1px solid #1e293b;border-radius:16px;overflow:hidden;margin:0 auto;align-items:flex-end;padding:6px 4px;transition:border-color 0.2s}
.search-box:focus-within{border-color:#2a3a6a}
.search-box textarea{flex:1;border:none;outline:none;background:none;color:#e2e8f0;font-size:15px;padding:14px 16px;resize:none;overflow:hidden;min-height:24px;max-height:120px;font-family:inherit;line-height:1.5;box-sizing:border-box;scrollbar-width:none;-ms-overflow-style:none}
.search-box textarea::placeholder{color:#475569}
.search-box textarea::-webkit-scrollbar{display:none}
.search-box button{width:38px;height:38px;border:none;background:#dfff00;color:#0a0f00;font-size:18px;font-weight:bold;cursor:pointer;border-radius:10px;margin:0 6px 6px 0;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:background 0.15s,transform 0.1s}
.search-box button:hover{background:#c8e600}
.search-box button:active{transform:scale(0.95)}
.search-box button:disabled{background:#2a3a00;color:#5a6a00;cursor:not-allowed}
.tool-page{flex:1;overflow-y:auto;padding:24px 48px}
.calculator-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px;max-width:920px;margin:0 auto}
.calc-card{background:#0c1635;border:1px solid #161f3a;border-radius:16px;padding:24px;transition:border-color 0.2s}
.calc-card:hover{border-color:#1e293b}
.calc-card h3{color:#dfff00;margin-bottom:16px;font-size:17px;font-weight:700}
.calc-input{width:100%;padding:11px 14px;background:#020817;border:1px solid #1e293b;border-radius:9px;color:#e2e8f0;font-size:15px;margin-bottom:12px;font-family:inherit;transition:border-color 0.2s}
.calc-input:focus{outline:none;border-color:#dfff00}
.calc-select{width:100%;padding:11px 14px;background:#020817;border:1px solid #1e293b;border-radius:9px;color:#e2e8f0;font-size:15px;margin-bottom:12px;cursor:pointer;font-family:inherit;transition:border-color 0.2s}
.calc-select:focus{outline:none;border-color:#dfff00}
.calc-btn{width:100%;padding:12px;background:#dfff00;border:none;border-radius:9px;color:#0a0f00;font-weight:700;cursor:pointer;font-size:15px;letter-spacing:0.1px;transition:background 0.15s,transform 0.1s}
.calc-btn:hover{background:#c8e600}
.calc-btn:active{transform:scale(0.99)}
.calc-result{margin-top:16px;padding:16px;background:#020817;border-radius:10px;border:1px solid #161f3a}
.calc-result-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #161f3a;font-size:14px}
.calc-result-row:last-child{border-bottom:none}
.calc-result-label{color:#64748b;font-weight:500}
.calc-result-value{color:#e2e8f0;font-weight:700}
.upload-area{border:2px dashed #1e293b;border-radius:16px;padding:48px 40px;text-align:center;cursor:pointer;transition:border-color 0.2s,background 0.2s}
.upload-area:hover{border-color:#dfff00;background:#0c1635}
.deadline-list{max-width:700px;margin:0 auto}
.deadline-item{background:#0c1635;border:1px solid #161f3a;border-radius:12px;padding:20px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center}
.deadline-date{color:#dfff00;font-weight:700;font-size:17px}
.deadline-name{color:#e2e8f0;font-size:15px;font-weight:500}
.deadline-status{padding:5px 12px;border-radius:20px;font-size:12px;font-weight:700}
.status-upcoming{background:#0c1635;color:#60a5fa;border:1px solid #1e3a5f}
.status-urgent{background:#450a0a;color:#f87171;border:1px solid #7f1d1d}
.setup-steps{max-width:700px;margin:0 auto}
.setup-step{display:flex;gap:18px;margin-bottom:28px}
.step-number{width:40px;height:40px;background:#dfff00;color:#0a0f00;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;flex-shrink:0;font-size:15px}
.step-content h3{color:#dfff00;margin-bottom:6px;font-weight:700}
.step-content p{color:#64748b;line-height:1.65}
.modal-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.75);display:flex;justify-content:center;align-items:center;z-index:1000;backdrop-filter:blur(2px)}
.modal-content{background:#070f26;padding:40px;border-radius:20px;width:420px;border:1px solid #1e293b;position:relative;box-shadow:0 24px 60px rgba(0,0,0,0.5)}
.modal-title{font-size:22px;font-weight:700;margin-bottom:20px;color:#e2e8f0;letter-spacing:-0.3px}
.modal-input{width:100%;padding:13px 15px;margin-top:10px;background:#020817;border:1px solid #1e293b;color:#e2e8f0;border-radius:10px;font-size:15px;font-family:inherit;transition:border-color 0.2s}
.modal-input:focus{outline:none;border-color:#dfff00}
.modal-btn{width:100%;padding:14px;margin-top:14px;background:#dfff00;border:none;border-radius:10px;font-weight:700;cursor:pointer;font-size:15px;color:#0a0f00;letter-spacing:0.1px;transition:background 0.15s}
.modal-btn:hover{background:#c8e600}
.modal-link{color:#dfff00;cursor:pointer;text-decoration:underline;font-weight:500}
.modal-close{position:absolute;top:18px;right:18px;background:none;border:none;color:#475569;font-size:22px;cursor:pointer;padding:4px;border-radius:6px;transition:color 0.15s}
.modal-close:hover{color:#e2e8f0}
.chat-area::-webkit-scrollbar,.chat-history::-webkit-scrollbar,.tool-page::-webkit-scrollbar{width:5px}
.chat-area::-webkit-scrollbar-thumb,.chat-history::-webkit-scrollbar-thumb,.tool-page::-webkit-scrollbar-thumb{background:#1e293b;border-radius:4px}
.hidden{display:none !important}
.tax-updates-container{max-width:1020px;margin:0 auto}
.tax-updates-tabs{display:flex;gap:2px;margin-bottom:24px;border-bottom:1px solid #161f3a;padding-bottom:0}
.tax-tab{padding:12px 22px;cursor:pointer;font-size:14px;font-weight:500;color:#64748b;border-bottom:2px solid transparent;margin-bottom:-1px;display:flex;align-items:center;gap:8px;transition:color 0.2s}
.tax-tab:hover{color:#e2e8f0}
.tax-tab.active{color:#dfff00;border-bottom-color:#dfff00;font-weight:600}
.tax-tab-badge{background:#ef4444;color:white;font-size:10px;padding:2px 7px;border-radius:10px;margin-left:4px;font-weight:700}
.news-filters{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
.news-filter-chip{padding:6px 14px;border-radius:20px;border:1px solid #1e293b;background:#0c1635;font-size:13px;cursor:pointer;display:flex;align-items:center;gap:6px;transition:all 0.15s;color:#94a3b8;font-weight:500}
.news-filter-chip:hover{background:#161f3a;color:#e2e8f0}
.news-filter-chip.active{background:#dfff00;color:#0a0f00;border-color:#dfff00;font-weight:700}
.news-grid{display:grid;gap:14px}
.news-card{background:#0c1635;border:1px solid #161f3a;border-radius:14px;padding:22px;transition:border-color 0.2s}
.news-card:hover{border-color:#1e293b}
.news-card.pinned{border-left:3px solid #dfff00}
.news-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;gap:12px}
.news-title{font-size:16px;font-weight:600;color:#e2e8f0;line-height:1.45;flex:1}
.news-badges{display:flex;gap:6px;flex-shrink:0;flex-wrap:wrap}
.news-badge{font-size:11px;padding:3px 9px;border-radius:20px;font-weight:600}
.badge-pinned{background:#450a0a;color:#f87171}
.badge-tz{background:#064e3b;color:#34d399}
.badge-ke{background:#1e3a8a;color:#60a5fa}
.badge-ug{background:#831843;color:#f472b6}
.badge-eac{background:#4a1d96;color:#c084fc}
.badge-admin{background:#7c2d12;color:#fdba74}
.badge-general{background:#1e293b;color:#94a3b8}
.news-meta{display:flex;gap:16px;font-size:12px;color:#475569;margin-bottom:12px;flex-wrap:wrap;font-weight:500}
.news-excerpt{font-size:14px;color:#64748b;line-height:1.65;margin-bottom:14px}
.news-actions{display:flex;gap:8px;flex-wrap:wrap}
.news-action{font-size:13px;color:#475569;cursor:pointer;display:flex;align-items:center;gap:4px;padding:5px 10px;border-radius:7px;transition:all 0.15s;font-weight:500}
.news-action:hover{background:#161f3a;color:#e2e8f0}
.news-action .icon{color:#dfff00}
.post-update-btn{background:#dfff00;color:#0a0f00;border:none;padding:10px 20px;border-radius:9px;font-weight:700;cursor:pointer;font-size:14px;display:flex;align-items:center;gap:6px;transition:background 0.15s,transform 0.1s}
.post-update-btn:hover{background:#c8e600}
.post-update-btn:disabled{background:#2a3a00;color:#5a6a00;cursor:not-allowed}
.compare-tool{background:#0c1635;border:1px solid #161f3a;border-radius:14px;padding:24px}
.compare-controls{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}
.control-group label{display:block;font-size:12px;font-weight:600;color:#64748b;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px}
.control-group select{width:100%;padding:10px 12px;background:#020817;border:1px solid #1e293b;border-radius:8px;color:#e2e8f0;font-size:14px;font-family:inherit}
.control-group select:focus{outline:none;border-color:#dfff00}
.country-checkboxes{display:flex;gap:12px;flex-wrap:wrap}
.country-check{display:flex;align-items:center;gap:8px;padding:8px 14px;border:1px solid #1e293b;border-radius:8px;cursor:pointer;font-size:14px;color:#94a3b8;transition:all 0.15s;font-weight:500}
.country-check:hover{background:#161f3a;color:#e2e8f0}
.country-check input{width:15px;height:15px;accent-color:#dfff00}
.compare-btn{width:100%;padding:12px;background:#dfff00;color:#0a0f00;border:none;border-radius:9px;font-weight:700;font-size:15px;cursor:pointer;margin-bottom:24px;transition:background 0.15s}
.compare-btn:hover{background:#c8e600}
.comparison-table{width:100%;border-collapse:collapse;margin-top:12px}
.comparison-table th,.comparison-table td{padding:13px 16px;text-align:left;border-bottom:1px solid #161f3a;font-size:14px}
.comparison-table th{background:#020817;font-weight:600;color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:0.5px}
.comparison-table td{color:#94a3b8}
.comparison-table tr:hover td{background:#070f26}
.comparison-table td strong{color:#e2e8f0}
.flag{font-size:18px;margin-right:6px}
.deadlines-list{display:grid;gap:12px}
.deadline-card{background:#0c1635;border:1px solid #161f3a;border-radius:14px;padding:20px;display:flex;gap:16px;align-items:flex-start;transition:border-color 0.2s}
.deadline-card:hover{border-color:#1e293b}
.deadline-icon{width:46px;height:46px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0}
.deadline-icon.urgent{background:#450a0a}
.deadline-icon.upcoming{background:#431407}
.deadline-icon.normal{background:#052e16}
.deadline-info{flex:1}
.deadline-title{font-size:15px;font-weight:600;color:#e2e8f0;margin-bottom:4px}
.deadline-desc{font-size:13px;color:#64748b;margin-bottom:8px}
.deadline-meta{display:flex;gap:16px;font-size:13px;flex-wrap:wrap;align-items:center}
.deadline-date{display:flex;align-items:center;gap:4px;color:#f87171;font-weight:600}
.deadline-date.safe{color:#34d399}
.deadline-date.warning{color:#fb923c}
.countdown{background:#431407;padding:4px 10px;border-radius:6px;font-size:12px;font-weight:700;color:#fbbf24}
.countdown.urgent{background:#450a0a;color:#f87171}
.countdown.safe{background:#052e16;color:#34d399}
.news-modal-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);display:flex;align-items:center;justify-content:center;z-index:1000;padding:20px;backdrop-filter:blur(2px)}
.news-modal{background:#0c1635;border:1px solid #1e293b;border-radius:18px;width:100%;max-width:620px;max-height:85vh;overflow-y:auto;padding:28px;position:relative;box-shadow:0 24px 60px rgba(0,0,0,0.5)}
.news-modal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px;padding-bottom:16px;border-bottom:1px solid #161f3a}
.news-modal-header h3{font-size:19px;color:#e2e8f0;font-weight:700}
.news-modal-close{background:none;border:none;color:#64748b;font-size:22px;cursor:pointer;padding:4px;border-radius:6px;transition:color 0.15s}
.news-modal-close:hover{color:#e2e8f0}
.form-group{margin-bottom:16px}
.form-group label{display:block;font-size:12px;font-weight:600;color:#64748b;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.4px}
.form-group input,.form-group textarea,.form-group select{width:100%;padding:10px 13px;background:#020817;border:1px solid #1e293b;border-radius:9px;color:#e2e8f0;font-size:14px;font-family:inherit;transition:border-color 0.2s}
.form-group textarea{min-height:120px;resize:vertical}
.form-group input:focus,.form-group textarea:focus,.form-group select:focus{outline:none;border-color:#dfff00}
.form-check{display:flex;align-items:center;gap:8px;color:#94a3b8;font-size:14px;cursor:pointer;font-weight:500}
.form-check input{width:15px;height:15px;accent-color:#dfff00}
.modal-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:22px}
.modal-btn{padding:9px 18px;border-radius:8px;border:1px solid #1e293b;background:#0c1635;color:#94a3b8;cursor:pointer;font-size:14px;font-family:inherit;font-weight:500;transition:all 0.15s}
.modal-btn:hover{background:#1e293b;color:#e2e8f0}
.modal-btn-primary{background:#dfff00;border-color:#dfff00;color:#0a0f00;font-weight:700}
.modal-btn-primary:hover{background:#c8e600}
.full-article-content{line-height:1.8;color:#e2e8f0;font-size:15px}
.full-article-content h2{color:#dfff00;margin:20px 0 10px;font-size:19px;font-weight:700}
.full-article-content p{margin:12px 0}
.full-article-content ul{margin:12px 0 12px 24px}
.full-article-content li{margin:6px 0}
.full-article-source{margin-top:20px;padding-top:16px;border-top:1px solid #161f3a;font-size:13px;color:#475569}
.full-article-source a{color:#dfff00;text-decoration:underline}
.tra-btn{background:#0c1635;border:1px solid #1e293b;color:#cbd5e1;padding:11px 14px;border-radius:10px;cursor:pointer;font-size:13px;text-align:left;transition:all 0.15s;width:100%;font-family:inherit;font-weight:500}
.tra-btn:hover{border-color:#dfff00;color:white;background:#111c44}
.tra-btn-yellow{color:#dfff00;border-color:#2a3a00}
.tra-btn-yellow:hover{background:#1a2a00;border-color:#dfff00}
.tra-btn-amber{color:#f59e0b;border-color:#3a2500}
.tra-btn-amber:hover{background:#1a1200;border-color:#f59e0b}
.tra-btn-red{color:#ef4444;border-color:#3a0000}
.tra-btn-red:hover{background:#1a0000;border-color:#ef4444}"""

with open(FILE, 'r') as f:
    content = f.read()

start = content.find('<style>')
end = content.find('</style>')

if start == -1 or end == -1:
    print('ERROR: Could not find <style> block')
else:
    content = content[:start + 7] + '\n' + NEW_CSS + '\n' + content[end:]
    print('✅ CSS replaced successfully')

with open(FILE, 'w') as f:
    f.write(content)
print('✅ Saved')
