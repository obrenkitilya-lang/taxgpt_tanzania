FILE = '/workspaces/taxgpt_tanzania/frontend/index_fixed.html'

with open(FILE, 'r') as f:
    content = f.read()

# Replace the entire userAuth div with correct HTML
OLD = '''    <div id="userAuth" style="display:none;flex-direction:column;border-top:1px solid #1e293b;">
      <div style="padding:10px 14px;cursor:pointer;" onclick="var d=document.getElementById('uDrop');d.style.display=d.style.display=='flex'?'none':'flex'">
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="width:32px;height:32px;border-radius:50%;background:#dfff00;color:#000;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;" id="userAvatar">O</div>
          <div style="flex:1;overflow:hidden;">
            <div id="userEmail" style="color:#e2e8f0;font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"></div>
            <div style="color:#64748b;font-size:11px;">Free</div>
          </div>
          <span style="color:#64748b;font-size:10px;">▲</span>
        </div>
      </div>
      <div id="uDrop" style="display:none;flex-direction:column;padding:4px 8px 8px;">
        <a href="/admin" id="adminLink" style="display:none;padding:7px 8px;color:#dfff00;font-size:13px;text-decoration:none;border-radius:6px;">🔒 Admin Panel</a>
        <a href="javascript:void(0)" onclick="showTool(\'account\')" style="padding:7px 8px;color:#e2e8f0;font-size:13px;text-decoration:none;display:block;border-radius:6px;">⚙️ My Account</a>
        <button onclick="logout()" style="padding:7px 8px;color:#ef4444;font-size:13px;background:none;border:none;text-align:left;cursor:pointer;border-radius:6px;font-family:inherit;">↪ Log out</button>
      </div>
    </div>'''

NEW = '''    <div id="userAuth" style="display:none;">
      <div class="user-menu-trigger" id="userMenuTrigger" onclick="toggleUserMenu()">
        <div class="user-avatar" id="userAvatar">O</div>
        <div class="user-menu-info">
          <div class="user-email" id="userEmail"></div>
          <div class="user-plan-badge" id="userPlanBadge">Free</div>
        </div>
        <svg id="userMenuChevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:#64748b;flex-shrink:0;transition:transform 0.2s;"><polyline points="18 15 12 9 6 15"></polyline></svg>
      </div>
      <div class="user-menu-dropdown" id="userMenuDropdown" style="display:none;">
        <div class="user-menu-header">
          <div style="font-size:12px;color:#64748b;font-weight:500;padding:4px 0 6px;" id="userMenuEmail"></div>
          <div id="userCountryBadge" style="font-size:11px;color:#dfff00;margin-bottom:2px;"></div>
          <div id="userRoleBadge" style="font-size:11px;color:#64748b;"></div>
        </div>
        <a href="javascript:void(0)" onclick="showTool(\'account\');toggleUserMenu()" class="user-menu-item">⚙️ My Account</a>
        <a href="/admin" class="user-menu-item" id="adminLink" style="display:none;">🔒 Admin Panel</a>
        <div class="user-menu-divider"></div>
        <button class="user-menu-item user-menu-logout" onclick="logout()">↪ Log out</button>
      </div>
    </div>'''

if OLD in content:
    content = content.replace(OLD, NEW)
    print('✅ userAuth HTML replaced')
else:
    print('❌ Could not find exact match - printing what is in file:')
    idx = content.find('id="userAuth"')
    print(content[idx:idx+500])

# Fix checkAuth to set display block not flex, and populate new fields
content = content.replace(
    "document.getElementById('userAuth').style.display = 'flex';",
    "document.getElementById('userAuth').style.display = 'block';"
)
content = content.replace(
    "document.getElementById('userAuth').style.display = 'block';\n      document.getElementById('userEmail').textContent = data.email;",
    """document.getElementById('userAuth').style.display = 'block';
      document.getElementById('userEmail').textContent = data.email;
      if (document.getElementById('userMenuEmail')) document.getElementById('userMenuEmail').textContent = data.email;
      const av = document.getElementById('userAvatar');
      if (av) av.textContent = (data.email || 'U')[0].toUpperCase();
      const planBadge = document.getElementById('userPlanBadge');
      if (planBadge) {
        if (data.role === 'admin') { planBadge.textContent = 'Admin'; planBadge.style.color = '#dfff00'; }
        else if (data.role === 'tax_professional') { planBadge.textContent = 'Tax Professional'; planBadge.style.color = '#60a5fa'; }
        else { planBadge.textContent = 'Free'; }
      }"""
)

# Fix adminLink display
content = content.replace(
    "document.getElementById('adminLink').style.display = 'block';",
    "document.getElementById('adminLink').style.display = 'block';"
)

with open(FILE, 'w') as f:
    f.write(content)
print('✅ Done! Now run: git add frontend/index_fixed.html && git commit -m "Fix user menu" && git push origin main')
