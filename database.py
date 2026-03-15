"""
database.py — Memory Only (No SQLite)
Bot restart হলে data যাবে, কিন্তু কোনো file error নেই।
"""
from datetime import datetime, date, timedelta

# ══════════════════════════════════════════════════════
#  In-Memory Storage
# ══════════════════════════════════════════════════════
_bots     = {}   # token -> bot info
_users    = {}   # (token, user_id) -> user info
_settings = {}   # (token, key) -> value
_channels = {}   # token -> [channel list]
_wds      = {}   # wd_id -> withdrawal info
_wd_seq   = [0]
_miles    = {}   # token -> [milestones]
_tickets  = {}   # ticket_id -> ticket info
_tkt_seq  = [0]


def init_db():
    print("✅ Memory DB ready!")


# ── Settings ──────────────────────────────────────────

def set_setting(token, key, value):
    _settings[(token, key)] = str(value)

def get_setting(token, key, default=None):
    return _settings.get((token, key), default)


# ── Child Bots ────────────────────────────────────────

def save_child_bot(owner_id, token, name, username):
    if token in _bots:
        return False
    _bots[token] = {
        'owner_id': owner_id, 'bot_token': token,
        'bot_name': name, 'bot_username': username,
        'is_active': 1, 'maintenance': 0,
        'welcome_photo': None, 'log_chat_id': None,
        'created_at': datetime.now().isoformat()
    }
    return True

def get_bot(token):
    return _bots.get(token)

def get_all_active_bots():
    return [b for b in _bots.values() if b.get('is_active')]

def get_user_bots(owner_id):
    return [b for b in _bots.values() if b['owner_id'] == owner_id]

def delete_child_bot(owner_id, token):
    if token in _bots and _bots[token]['owner_id'] == owner_id:
        del _bots[token]
        return True
    return False

def set_maintenance(token, on):
    if token in _bots:
        _bots[token]['maintenance'] = 1 if on else 0

def set_welcome_photo(token, file_id):
    if token in _bots:
        _bots[token]['welcome_photo'] = file_id

def set_log_chat(token, chat_id):
    if token in _bots:
        _bots[token]['log_chat_id'] = str(chat_id)


# ── Users ─────────────────────────────────────────────

def register_user(token, user_id, username, first_name, referred_by=None, level1_ref=None):
    key = (token, user_id)
    if key in _users:
        return False
    _users[key] = {
        'bot_token': token, 'user_id': user_id,
        'username': username, 'first_name': first_name,
        'referred_by': referred_by, 'level1_ref': level1_ref,
        'balance': 0.0, 'total_refs': 0, 'level2_refs': 0,
        'is_banned': 0, 'wallet': None, 'wallet_locked': 0,
        'last_daily': None, 'daily_streak': 0,
        'joined_at': datetime.now().isoformat()
    }
    bonus  = float(get_setting(token, 'ref_bonus', 10))
    bonus2 = float(get_setting(token, 'ref_bonus_l2', 2))
    if referred_by:
        rkey = (token, referred_by)
        if rkey in _users:
            _users[rkey]['balance']    += bonus
            _users[rkey]['total_refs'] += 1
            _check_milestone(token, referred_by)
    if level1_ref:
        lkey = (token, level1_ref)
        if lkey in _users:
            _users[lkey]['balance']     += bonus2
            _users[lkey]['level2_refs'] += 1
    return True

def _check_milestone(token, user_id):
    key  = (token, user_id)
    refs = _users[key]['total_refs']
    for ms in _miles.get(token, []):
        if ms['ref_count'] == refs:
            _users[key]['balance'] += ms['bonus']

def get_user(token, user_id):
    return _users.get((token, user_id))

def get_all_users(token):
    return [u for k, u in _users.items() if k[0] == token]

def ban_user(token, user_id):
    key = (token, user_id)
    if key in _users:
        _users[key]['is_banned'] = 1

def unban_user(token, user_id):
    key = (token, user_id)
    if key in _users:
        _users[key]['is_banned'] = 0

def add_balance_db(token, user_id, amount):
    key = (token, user_id)
    if key in _users:
        _users[key]['balance'] += amount

def set_user_wallet(token, user_id, wallet):
    key = (token, user_id)
    if key in _users:
        _users[key]['wallet']        = wallet
        _users[key]['wallet_locked'] = 1

def get_leaderboard(token, limit=10):
    users = get_all_users(token)
    users = [u for u in users if not u.get('is_banned')]
    users.sort(key=lambda u: u['total_refs'], reverse=True)
    return users[:limit]

def get_db_stats(token):
    users = get_all_users(token)
    wds   = [w for w in _wds.values() if w['bot_token'] == token]
    return {
        'total_users':         len(users),
        'total_balance':       sum(u['balance'] for u in users),
        'total_refs':          sum(u['total_refs'] for u in users),
        'pending_withdrawals': len([w for w in wds if w['status'] == 'pending']),
        'total_paid':          sum(w['amount'] for w in wds if w['status'] == 'approved'),
        'banned_users':        len([u for u in users if u.get('is_banned')]),
        'open_tickets':        len([t for t in _tickets.values() if t['bot_token'] == token and t['status'] == 'open']),
    }


# ── Daily Bonus ───────────────────────────────────────

def claim_daily(token, user_id):
    key  = (token, user_id)
    if key not in _users:
        return False, 0, 0
    u     = _users[key]
    today = date.today().strftime('%Y-%m-%d')
    if u['last_daily'] == today:
        return False, 0, u['daily_streak']
    yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    streak    = (u['daily_streak'] + 1) if u['last_daily'] == yesterday else 1
    base      = float(get_setting(token, 'daily_bonus', 2))
    bonus     = round(base + (streak - 1) * 0.5, 2)
    u['balance']     += bonus
    u['last_daily']   = today
    u['daily_streak'] = streak
    return True, bonus, streak


# ── Force Channels ────────────────────────────────────

def add_channel(token, channel_id, name, invite):
    if token not in _channels:
        _channels[token] = []
    for ch in _channels[token]:
        if ch['channel_id'] == str(channel_id):
            return False
    _channels[token].append({
        'channel_id': str(channel_id),
        'channel_name': name,
        'invite_link': invite
    })
    return True

def remove_channel(token, channel_id):
    if token in _channels:
        _channels[token] = [c for c in _channels[token] if c['channel_id'] != str(channel_id)]

def get_channels(token):
    return _channels.get(token, [])


# ── Withdrawals ───────────────────────────────────────

def create_withdrawal(token, user_id, amount, method, address):
    key = (token, user_id)
    if key in _users:
        _users[key]['balance'] -= amount
    _wd_seq[0] += 1
    wid = _wd_seq[0]
    _wds[wid] = {
        'id': wid, 'bot_token': token, 'user_id': user_id,
        'amount': amount, 'method': method, 'address': address,
        'status': 'pending', 'reject_reason': '',
        'created_at': datetime.now().isoformat()
    }
    return wid

def get_pending_withdrawals(token):
    result = []
    for w in _wds.values():
        if w['bot_token'] == token and w['status'] == 'pending':
            u = get_user(token, w['user_id']) or {}
            row = dict(w)
            row['username']   = u.get('username')
            row['first_name'] = u.get('first_name')
            result.append(row)
    return result

def update_withdrawal(wid, status, reason=''):
    if wid in _wds:
        _wds[wid]['status']        = status
        _wds[wid]['reject_reason'] = reason
        if status == 'rejected':
            w   = _wds[wid]
            key = (w['bot_token'], w['user_id'])
            if key in _users:
                _users[key]['balance'] += w['amount']

def get_withdrawal(wid):
    return _wds.get(wid)


# ── Milestones ────────────────────────────────────────

def add_milestone(token, ref_count, bonus):
    if token not in _miles:
        _miles[token] = []
    _miles[token].append({'ref_count': ref_count, 'bonus': bonus})
    _miles[token].sort(key=lambda m: m['ref_count'])
    return True

def get_milestones(token):
    return _miles.get(token, [])


# ── Tickets ───────────────────────────────────────────

def create_ticket(token, user_id, message):
    _tkt_seq[0] += 1
    tid = _tkt_seq[0]
    u   = get_user(token, user_id) or {}
    _tickets[tid] = {
        'id': tid, 'bot_token': token, 'user_id': user_id,
        'message': message, 'status': 'open', 'reply': None,
        'username': u.get('username'), 'first_name': u.get('first_name'),
        'created_at': datetime.now().isoformat()
    }
    return tid

def get_open_tickets(token):
    return [t for t in _tickets.values() if t['bot_token'] == token and t['status'] == 'open']

def reply_ticket(tid, reply_text):
    if tid in _tickets:
        _tickets[tid]['reply']  = reply_text
        _tickets[tid]['status'] = 'closed'
    
