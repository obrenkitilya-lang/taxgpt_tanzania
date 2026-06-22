import re

HTML_FILE = '/workspaces/taxgpt_tanzania/frontend/index_fixed.html'
APP_FILE  = '/workspaces/taxgpt_tanzania/app.py'

with open(HTML_FILE, 'r') as f:
    html = f.read()
with open(APP_FILE, 'r') as f:
    app = f.read()

errors = []

ACCOUNT_BTN = '\n      <button class="auth-btn" id="myAccountBtn" onclick="window.location.href=\'/account\'" style="display:none;margin-bottom:8px;">⚙️ My Account</button>'
ADMIN_LINK = '      <a href="/admin" class="auth-btn" id="adminLink" style="display:none;margin-bottom:8px;">🔒 Admin Panel</a>'
if 'myAccountBtn' in html:
    print('✅ My Account button already present')
elif ADMIN_LINK in html:
    html = html.replace(ADMIN_LINK, ADMIN_LINK + ACCOUNT_BTN)
    print('✅ My Account button added')
else:
    errors.append('No Admin Panel link found')

ACCOUNT_PAGE = '''  <div class="tool-page hidden" id="accountPage">
    <div style="max-width:600px;margin:0 auto;padding:20px;">
      <h2 style="color:#dfff00;margin-bottom:8px;font-size:28px;">⚙️ My Account</h2>
      <p style="color:#64748b;margin-bottom:30px;">Manage your account settings</p>
      <div class="calc-card" style="margin-bottom:20px;">
        <h3 style="margin-bottom:16px;">🌍 Change Country</h3>
        <p style="color:#64748b;font-size:13px;margin-bottom:12px;">Update your country for relevant tax information.</p>
        <select id="accountCountry" style="width:100%;background:#0f172a;color:white;border:1px solid #334155;padding:10px 14px;border-radius:8px;font-size:14px;margin-bottom:12px;">
          <option value="Tanzania">🇹🇿 Tanzania</option>
          <option value="Kenya">🇰🇪 Kenya</option>
          <option value="Uganda">🇺🇬 Uganda</option>
        </select>
        <button onclick="accountChangeCountry()" style="background:#dfff00;color:#000;border:none;padding:10px 24px;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px;">Update Country</button>
        <div id="countryMsg" style="margin-top:10px;font-size:13px;"></div>
      </div>
      <div class="calc-card" style="margin-bottom:20px;">
        <h3 style="margin-bottom:16px;">🔑 Change Password</h3>
        <input type="password" id="accCurrentPwd" placeholder="Current password" style="width:100%;background:#0f172a;color:white;border:1px solid #334155;padding:10px 14px;border-radius:8px;font-size:14px;margin-bottom:10px;box-sizing:border-box;">
        <input type="password" id="accNewPwd" placeholder="New password (min 6 chars)" style="width:100%;background:#0f172a;color:white;border:1px solid #334155;padding:10px 14px;border-radius:8px;font-size:14px;margin-bottom:10px;box-sizing:border-box;">
        <input type="password" id="accConfirmPwd" placeholder="Confirm new password" style="width:100%;background:#0f172a;color:white;border:1px solid #334155;padding:10px 14px;border-radius:8px;font-size:14px;margin-bottom:12px;box-sizing:border-box;">
        <button onclick="accountChangePassword()" style="background:#dfff00;color:#000;border:none;padding:10px 24px;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px;">Change Password</button>
        <div id="passwordMsg" style="margin-top:10px;font-size:13px;"></div>
      </div>
      <div class="calc-card" style="margin-bottom:20px;border-color:#ef4444;">
        <h3 style="margin-bottom:8px;color:#ef4444;">🗑️ Delete Account</h3>
        <p style="color:#64748b;font-size:13px;margin-bottom:12px;">This will permanently delete your account and all your data. This cannot be undone.</p>
        <input type="password" id="accDeletePwd" placeholder="Enter your password to confirm" style="width:100%;background:#0f172a;color:white;border:1px solid #ef4444;padding:10px 14px;border-radius:8px;font-size:14px;margin-bottom:12px;box-sizing:border-box;">
        <button onclick="accountDelete()" style="background:#ef4444;color:white;border:none;padding:10px 24px;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px;">Delete My Account</button>
        <div id="deleteMsg" style="margin-top:10px;font-size:13px;"></div>
      </div>
    </div>
  </div>

'''

ADMIN_PAGE_ANCHOR = '  <div class="tool-page hidden" id="adminPage">'
if 'id="accountPage"' in html:
    print('✅ accountPage already present')
elif ADMIN_PAGE_ANCHOR in html:
    html = html.replace(ADMIN_PAGE_ANCHOR, ACCOUNT_PAGE + ADMIN_PAGE_ANCHOR)
    print('✅ accountPage added')
else:
    errors.append('No adminPage anchor found')

OLD_ROUTE = "else if (currentTool === 'admin') { showPage('adminPage'); }\nelse showPage('chatPage');"
NEW_ROUTE = "else if (currentTool === 'admin') { showPage('adminPage'); }\nelse if (currentTool === 'account') { showPage('accountPage'); }\nelse showPage('chatPage');"
if "currentTool === 'account'" in html:
    print('✅ account routing already present')
elif OLD_ROUTE in html:
    html = html.replace(OLD_ROUTE, NEW_ROUTE)
    print('✅ account routing added')
else:
    errors.append('No routing block found')

OLD_AUTH = "      if (data.role === 'admin') {"
NEW_AUTH = "      document.getElementById('myAccountBtn').style.display = 'block';\n      if (data.role === 'admin') {"
if "myAccountBtn').style.display" in html:
    print('✅ myAccountBtn show already wired')
elif OLD_AUTH in html:
    html = html.replace(OLD_AUTH, NEW_AUTH, 1)
    print('✅ myAccountBtn wired')
else:
    errors.append('No checkAuth block found')

ACCOUNT_JS = """
function accountChangeCountry() {
  const country = document.getElementById('accountCountry').value;
  const msg = document.getElementById('countryMsg');
  fetch('/api/account/change-country', {
    method: 'POST', headers: {'Content-Type':'application/json'}, credentials: 'include',
    body: JSON.stringify({country})
  }).then(r => r.json()).then(data => {
    if (data.error) { msg.style.color='#f87171'; msg.textContent = data.error; }
    else { msg.style.color='#4ade80'; msg.textContent = 'Country updated to ' + data.country; document.getElementById('userCountryBadge').textContent = data.country; }
  }).catch(() => { msg.style.color='#f87171'; msg.textContent = 'Network error'; });
}
function accountChangePassword() {
  const current = document.getElementById('accCurrentPwd').value;
  const newPwd = document.getElementById('accNewPwd').value;
  const confirm = document.getElementById('accConfirmPwd').value;
  const msg = document.getElementById('passwordMsg');
  if (newPwd !== confirm) { msg.style.color='#f87171'; msg.textContent = 'New passwords do not match'; return; }
  fetch('/api/account/change-password', {
    method: 'POST', headers: {'Content-Type':'application/json'}, credentials: 'include',
    body: JSON.stringify({current_password: current, new_password: newPwd})
  }).then(r => r.json()).then(data => {
    if (data.error) { msg.style.color='#f87171'; msg.textContent = data.error; }
    else { msg.style.color='#4ade80'; msg.textContent = 'Password changed successfully'; document.getElementById('accCurrentPwd').value=''; document.getElementById('accNewPwd').value=''; document.getElementById('accConfirmPwd').value=''; }
  }).catch(() => { msg.style.color='#f87171'; msg.textContent = 'Network error'; });
}
function accountDelete() {
  const pwd = document.getElementById('accDeletePwd').value;
  const msg = document.getElementById('deleteMsg');
  if (!confirm('Are you sure you want to permanently delete your account? This cannot be undone.')) return;
  fetch('/api/account/delete', {
    method: 'DELETE', headers: {'Content-Type':'application/json'}, credentials: 'include',
    body: JSON.stringify({password: pwd})
  }).then(r => r.json()).then(data => {
    if (data.error) { msg.style.color='#f87171'; msg.textContent = data.error; }
    else { alert('Your account has been deleted.'); window.location.href = '/'; }
  }).catch(() => { msg.style.color='#f87171'; msg.textContent = 'Network error'; });
}
"""

if 'function accountChangeCountry' in html:
    print('✅ Account JS already present')
else:
    idx = html.rfind('</script>')
    html = html[:idx] + ACCOUNT_JS + html[idx:]
    print('✅ Account JS injected')

OLD_TOOLS = "valid_tools = ['tax_updates', 'documents', 'calculators', 'deadlines', 'business_setup', 'tax_research']"
NEW_TOOLS = "valid_tools = ['tax_updates', 'documents', 'calculators', 'deadlines', 'business_setup', 'tax_research', 'account']"
if "'account'" in app:
    print('✅ account in valid_tools already')
elif OLD_TOOLS in app:
    app = app.replace(OLD_TOOLS, NEW_TOOLS)
    print('✅ account added to valid_tools')
else:
    errors.append('No valid_tools in app.py')

ACCOUNT_ROUTES = '''
@app.route("/api/account/change-password", methods=["POST"])
@login_required
def change_password():
    try:
        data = request.get_json()
        current_password = data.get("current_password", "")
        new_password = data.get("new_password", "")
        if not current_password or not new_password:
            return jsonify({"error": "Both current and new password are required"}), 400
        if len(new_password) < 6:
            return jsonify({"error": "New password must be at least 6 characters"}), 400
        if not check_password_hash(current_user.password, current_password):
            return jsonify({"error": "Current password is incorrect"}), 401
        current_user.password = generate_password_hash(new_password)
        db.session.commit()
        return jsonify({"message": "Password changed successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/account/change-country", methods=["POST"])
@login_required
def change_country():
    try:
        data = request.get_json()
        country = data.get("country", "").strip()
        if country not in ["Tanzania", "Kenya", "Uganda"]:
            return jsonify({"error": "Country must be Tanzania, Kenya, or Uganda"}), 400
        current_user.country = country
        db.session.commit()
        return jsonify({"message": "Country updated successfully", "country": country})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/account/delete", methods=["DELETE"])
@login_required
def delete_account():
    try:
        data = request.get_json() or {}
        password = data.get("password", "")
        if not check_password_hash(current_user.password, password):
            return jsonify({"error": "Incorrect password"}), 401
        user_id = current_user.id
        logout_user()
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
        return jsonify({"message": "Account deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
'''

LOGOUT_ROUTE = 'def api_logout():\n    logout_user()\n    return jsonify({"message": "Logged out successfully"})'
if 'api/account/change-password' in app:
    print('✅ Account routes already in app.py')
elif LOGOUT_ROUTE in app:
    app = app.replace(LOGOUT_ROUTE, LOGOUT_ROUTE + '\n' + ACCOUNT_ROUTES)
    print('✅ Account routes added to app.py')
else:
    errors.append('No logout route anchor in app.py')

if errors:
    print('\n ISSUES:')
    for e in errors: print(' -', e)
else:
    print('\n✅ All patches applied!')

with open(HTML_FILE, 'w') as f: f.write(html)
print('✅ Saved HTML')
with open(APP_FILE, 'w') as f: f.write(app)
print('✅ Saved app.py')
