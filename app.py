from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import sqlite3
import os
import hashlib
import secrets
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
DATABASE = 'inventory.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'shop',
                is_super_admin INTEGER DEFAULT 0,
                shop_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER NOT NULL,
                barcode TEXT NOT NULL,
                brand TEXT NOT NULL,
                product_type TEXT NOT NULL,
                model TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(shop_id, barcode),
                FOREIGN KEY (shop_id) REFERENCES users(id)
            )
        ''')
        # Create super admin if not exists
        admin = conn.execute("SELECT * FROM users WHERE username='admin'").fetchone()
        if not admin:
            conn.execute(
                "INSERT INTO users (username, password, role, is_super_admin, shop_name) VALUES (?, ?, 'admin', 1, ?)",
                ('admin', hash_password('admin123'), 'Super Admin')
            )
        conn.commit()

# ── Auth helpers ──────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not session.get('is_super_admin'):
            flash('Only the Super Admin can do this', 'error')
            return redirect(url_for('admin_panel'))
        return f(*args, **kwargs)
    return decorated

# ── Auth routes ───────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard') if session.get('role') != 'admin' else url_for('admin_panel'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username=? AND password=?",
                (username, hash_password(password))
            ).fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['shop_name'] = user['shop_name']
            session['is_super_admin'] = bool(user['is_super_admin'])
            return redirect(url_for('admin_panel') if user['role'] == 'admin' else url_for('dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── Admin panel ───────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin_panel():
    with get_db() as conn:
        shops = conn.execute(
            """SELECT u.*, COUNT(p.id) as product_count, COALESCE(SUM(p.quantity),0) as total_stock
               FROM users u LEFT JOIN products p ON u.id=p.shop_id
               WHERE u.role='shop' GROUP BY u.id ORDER BY u.created_at DESC"""
        ).fetchall()
        admins = conn.execute(
            "SELECT * FROM users WHERE role='admin' ORDER BY is_super_admin DESC, created_at"
        ).fetchall()
    return render_template('admin.html', shops=shops, admins=admins)

# Add shop
@app.route('/admin/add-shop', methods=['POST'])
@admin_required
def add_shop():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    shop_name = request.form.get('shop_name', '').strip()
    if not all([username, password, shop_name]):
        flash('All fields required', 'error')
        return redirect(url_for('admin_panel'))
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (username, password, role, shop_name) VALUES (?, ?, 'shop', ?)",
                (username, hash_password(password), shop_name)
            )
            conn.commit()
        flash(f'Shop "{shop_name}" created!', 'success')
    except sqlite3.IntegrityError:
        flash('Username already exists', 'error')
    return redirect(url_for('admin_panel'))

# Delete shop — super admin only
@app.route('/admin/delete-shop/<int:shop_id>', methods=['POST'])
@super_admin_required
def delete_shop(shop_id):
    with get_db() as conn:
        conn.execute("DELETE FROM products WHERE shop_id=?", (shop_id,))
        conn.execute("DELETE FROM users WHERE id=? AND role='shop'", (shop_id,))
        conn.commit()
    flash('Shop deleted', 'success')
    return redirect(url_for('admin_panel'))

# Reset shop password
@app.route('/admin/reset-password/<int:user_id>', methods=['POST'])
@admin_required
def reset_password(user_id):
    new_password = request.form.get('new_password', '').strip()
    if not new_password:
        flash('Password cannot be empty', 'error')
        return redirect(url_for('admin_panel'))
    # Only super admin can reset another admin's password
    with get_db() as conn:
        target = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not target:
            flash('User not found', 'error')
            return redirect(url_for('admin_panel'))
        if target['role'] == 'admin' and not session.get('is_super_admin'):
            flash('Only Super Admin can reset admin passwords', 'error')
            return redirect(url_for('admin_panel'))
        conn.execute("UPDATE users SET password=? WHERE id=?", (hash_password(new_password), user_id))
        conn.commit()
    flash('Password reset successfully', 'success')
    return redirect(url_for('admin_panel'))

# Change own password
@app.route('/admin/change-my-password', methods=['POST'])
@admin_required
def change_my_password():
    current = request.form.get('current_password', '').strip()
    new_pw = request.form.get('new_password', '').strip()
    confirm = request.form.get('confirm_password', '').strip()
    if not all([current, new_pw, confirm]):
        flash('All password fields required', 'error')
        return redirect(url_for('admin_panel'))
    if new_pw != confirm:
        flash('New passwords do not match', 'error')
        return redirect(url_for('admin_panel'))
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id=? AND password=?",
            (session['user_id'], hash_password(current))
        ).fetchone()
        if not user:
            flash('Current password is wrong', 'error')
            return redirect(url_for('admin_panel'))
        conn.execute("UPDATE users SET password=? WHERE id=?", (hash_password(new_pw), session['user_id']))
        conn.commit()
    flash('Your password changed successfully!', 'success')
    return redirect(url_for('admin_panel'))

# Add admin — super admin only
@app.route('/admin/add-admin', methods=['POST'])
@super_admin_required
def add_admin():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    name = request.form.get('admin_name', '').strip()
    if not all([username, password, name]):
        flash('All fields required', 'error')
        return redirect(url_for('admin_panel'))
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (username, password, role, is_super_admin, shop_name) VALUES (?, ?, 'admin', 0, ?)",
                (username, hash_password(password), name)
            )
            conn.commit()
        flash(f'Admin "{name}" created!', 'success')
    except sqlite3.IntegrityError:
        flash('Username already exists', 'error')
    return redirect(url_for('admin_panel'))

# Delete admin — super admin only
@app.route('/admin/delete-admin/<int:admin_id>', methods=['POST'])
@super_admin_required
def delete_admin(admin_id):
    if admin_id == session['user_id']:
        flash('Cannot delete yourself', 'error')
        return redirect(url_for('admin_panel'))
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id=? AND role='admin' AND is_super_admin=0", (admin_id,))
        conn.commit()
    flash('Admin deleted', 'success')
    return redirect(url_for('admin_panel'))

# View any shop's inventory
@app.route('/admin/view-shop/<int:shop_id>')
@admin_required
def view_shop(shop_id):
    with get_db() as conn:
        shop = conn.execute("SELECT * FROM users WHERE id=?", (shop_id,)).fetchone()
        products = conn.execute("SELECT * FROM products WHERE shop_id=? ORDER BY brand", (shop_id,)).fetchall()
        total = len(products)
        low_stock = sum(1 for p in products if 0 < p['quantity'] <= 3)
        out_of_stock = sum(1 for p in products if p['quantity'] == 0)
        total_units = sum(p['quantity'] for p in products)
    return render_template('admin_shop_view.html', shop=shop, products=products,
                           total=total, low_stock=low_stock, out_of_stock=out_of_stock, total_units=total_units)

# ── Shop routes ───────────────────────────────────────────
@app.route('/')
@login_required
def dashboard():
    if session.get('role') == 'admin':
        return redirect(url_for('admin_panel'))
    shop_id = session['user_id']
    with get_db() as conn:
        total = conn.execute('SELECT COUNT(*) FROM products WHERE shop_id=?', (shop_id,)).fetchone()[0]
        low_stock = conn.execute('SELECT COUNT(*) FROM products WHERE shop_id=? AND quantity<=3 AND quantity>0', (shop_id,)).fetchone()[0]
        out_of_stock = conn.execute('SELECT COUNT(*) FROM products WHERE shop_id=? AND quantity=0', (shop_id,)).fetchone()[0]
        recent = conn.execute('SELECT * FROM products WHERE shop_id=? ORDER BY created_at DESC LIMIT 5', (shop_id,)).fetchall()
    return render_template('dashboard.html', total=total, low_stock=low_stock, out_of_stock=out_of_stock, recent=recent)

@app.route('/add')
@login_required
def add_page():
    return render_template('add_stock.html')

@app.route('/inventory')
@login_required
def inventory_page():
    shop_id = session['user_id']
    query = request.args.get('q', '')
    with get_db() as conn:
        if query:
            products = conn.execute(
                'SELECT * FROM products WHERE shop_id=? AND (barcode LIKE ? OR brand LIKE ? OR model LIKE ?) ORDER BY brand',
                (shop_id, f'%{query}%', f'%{query}%', f'%{query}%')
            ).fetchall()
        else:
            products = conn.execute('SELECT * FROM products WHERE shop_id=? ORDER BY brand', (shop_id,)).fetchall()
    return render_template('inventory.html', products=products, query=query)

@app.route('/stock-out')
@login_required
def stock_out_page():
    return render_template('stock_out.html')

# ── Product API ───────────────────────────────────────────
@app.route('/api/products', methods=['POST'])
@login_required
def add_product():
    shop_id = session['user_id']
    data = request.json
    barcode = data.get('barcode', '').strip()
    brand = data.get('brand', '').strip()
    product_type = data.get('product_type', '').strip()
    model = data.get('model', '').strip()
    quantity = int(data.get('quantity', 1))
    if not all([barcode, brand, product_type, model]):
        return jsonify({'success': False, 'error': 'All fields are required'}), 400
    try:
        with get_db() as conn:
            existing = conn.execute('SELECT * FROM products WHERE shop_id=? AND barcode=?', (shop_id, barcode)).fetchone()
            if existing:
                return jsonify({'success': False, 'error': f'Barcode already exists: {existing["brand"]} {existing["model"]}'}), 409
            conn.execute(
                'INSERT INTO products (shop_id, barcode, brand, product_type, model, quantity) VALUES (?,?,?,?,?,?)',
                (shop_id, barcode, brand, product_type, model, quantity)
            )
            conn.commit()
        return jsonify({'success': True, 'message': 'Product added successfully'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Barcode already exists'}), 409

@app.route('/api/products/scan/<barcode>')
@login_required
def get_by_barcode(barcode):
    shop_id = session['user_id']
    with get_db() as conn:
        product = conn.execute('SELECT * FROM products WHERE shop_id=? AND barcode=?', (shop_id, barcode)).fetchone()
    if product:
        return jsonify({'success': True, 'product': dict(product)})
    return jsonify({'success': False, 'error': 'Product not found'}), 404

@app.route('/api/products/<int:product_id>', methods=['PUT'])
@login_required
def update_product(product_id):
    shop_id = session['user_id']
    data = request.json
    with get_db() as conn:
        conn.execute(
            'UPDATE products SET brand=?, product_type=?, model=?, quantity=? WHERE id=? AND shop_id=?',
            (data.get('brand'), data.get('product_type'), data.get('model'), int(data.get('quantity', 0)), product_id, shop_id)
        )
        conn.commit()
    return jsonify({'success': True})

@app.route('/api/products/stock-out/<barcode>', methods=['POST'])
@login_required
def stock_out(barcode):
    shop_id = session['user_id']
    with get_db() as conn:
        product = conn.execute('SELECT * FROM products WHERE shop_id=? AND barcode=?', (shop_id, barcode)).fetchone()
        if not product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404
        new_qty = product['quantity'] - 1
        if new_qty <= 0:
            conn.execute('DELETE FROM products WHERE barcode=? AND shop_id=?', (barcode, shop_id))
            conn.commit()
            return jsonify({'success': True, 'message': f'{product["brand"]} {product["model"]} removed', 'removed': True})
        conn.execute('UPDATE products SET quantity=? WHERE barcode=? AND shop_id=?', (new_qty, barcode, shop_id))
        conn.commit()
        return jsonify({'success': True, 'message': f'Remaining: {new_qty}', 'removed': False, 'new_qty': new_qty})

@app.route('/api/stats')
@login_required
def api_stats():
    shop_id = session['user_id']
    with get_db() as conn:
        total = conn.execute('SELECT COUNT(*) FROM products WHERE shop_id=?', (shop_id,)).fetchone()[0]
        low_stock = conn.execute('SELECT COUNT(*) FROM products WHERE shop_id=? AND quantity<=3 AND quantity>0', (shop_id,)).fetchone()[0]
        out_of_stock = conn.execute('SELECT COUNT(*) FROM products WHERE shop_id=? AND quantity=0', (shop_id,)).fetchone()[0]
        total_items = conn.execute('SELECT COALESCE(SUM(quantity),0) FROM products WHERE shop_id=?', (shop_id,)).fetchone()[0]
    return jsonify({'total': total, 'low_stock': low_stock, 'out_of_stock': out_of_stock, 'total_items': total_items})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
