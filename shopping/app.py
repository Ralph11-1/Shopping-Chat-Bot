from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3, os
from werkzeug.utils import secure_filename
import serial
import pyttsx3
import time
import pyttsx3

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'static/uploads'
LOCATION_FOLDER = 'static/locations'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LOCATION_FOLDER, exist_ok=True)

def get_db():
    conn = sqlite3.connect('ecommerce.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            password TEXT,
            role TEXT
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price REAL,
            image TEXT,
            location_image TEXT,
            rpath TEXT
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")
        db.commit()
        admin = db.execute("SELECT * FROM users WHERE email='admin@admin.com'").fetchone()
        if not admin:
            db.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",('Admin', 'admin@admin.com', 'admin123', 'admin'))
            db.commit()

@app.route('/')
def index():
    db = get_db()
    products = db.execute('SELECT * FROM products').fetchall()
    return render_template('index.html', products=products)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        db = get_db()
        db.execute('INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)',
                   (request.form['name'], request.form['email'], request.form['password'], 'customer'))
        db.commit()
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email=? AND password=? AND role=?',
                          (request.form['email'], request.form['password'], request.form['role'])).fetchone()
        if user:
            session['user'] = dict(user)
            return redirect('/admin' if user['role'] == 'admin' else '/customer')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/admin')
def admin_dashboard():
    db = get_db()
    products = db.execute('SELECT * FROM products').fetchall()
    return render_template('admin_dashboard.html', products=products)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        file = request.files['image']
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        db = get_db()
        db.execute('INSERT INTO products (name, price, image) VALUES (?, ?, ?)',
                   (request.form['name'], request.form['price'], filename))
        db.commit()
        return redirect('/')
    return render_template('add_product.html')

@app.route('/add_product_location', methods=['GET', 'POST'])
def add_product_location():
    db = get_db()
    products = db.execute('SELECT * FROM products').fetchall()
    if request.method == 'POST':
        product_id = request.form['product_id']
        file = request.files['location_image']
        desc=request.form['desc']
        filename = secure_filename(file.filename)
        file.save(os.path.join(LOCATION_FOLDER, filename))
        db.execute('UPDATE products SET location_image=?,rpath=? WHERE id=?', (filename,desc, product_id))
        db.commit()
        return redirect('/')
    return render_template('add_product_location.html', products=products)

@app.route('/customer')
def customer_dashboard():
    return render_template('customer_dashboard.html')

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    cart = session.get('cart', {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    session['cart'] = cart
    return redirect('/')

@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    db = get_db()
    products = db.execute('SELECT * FROM products').fetchall()
    product_dict = {str(p['id']): p for p in products}
    cart_items, total = [], 0
    for pid, qty in cart.items():
        if pid in product_dict:
            prod = product_dict[pid]
            subtotal = qty * prod['price']
            cart_items.append({'id': pid, 'name': prod['name'], 'price': prod['price'], 'qty': qty, 'subtotal': subtotal})
            total += subtotal
    return render_template('cart.html', cart=cart_items, total=total)

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    cart.pop(str(product_id), None)
    session['cart'] = cart
    return redirect('/cart')

@app.route('/place_order')
def place_order():
    if 'user' not in session:
        return redirect('/login')
    db = get_db()
    uid = session['user']['id']
    cart = session.get('cart', {})
    for pid, qty in cart.items():
        db.execute('INSERT INTO orders (user_id, product_id, quantity) VALUES (?, ?, ?)',
                   (uid, pid, qty))
    db.commit()
    session['cart'] = {}
    return redirect('/orders')

@app.route('/orders')
def orders():
    if 'user' not in session:
        return redirect('/login')
    db = get_db()
    rows = db.execute('''
        SELECT p.name, o.quantity, p.price, o.quantity * p.price AS total
        FROM orders o JOIN products p ON o.product_id = p.id
        WHERE o.user_id = ?
    ''', (session['user']['id'],)).fetchall()
    return render_template('orders.html', orders=rows)

@app.route('/product_location/<int:product_id>')
def product_location(product_id):
    db = get_db()
    product = db.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    print(product['rpath'])
    arduino = serial.Serial('COM9', 9600, timeout=1)  # Replace 'COM3' with your Arduino's port (e.g., '/dev/ttyACM0' for Linux or 'COMx' for Windows)
    time.sleep(4)
    message_to_send=product['rpath']
    arduino.write(message_to_send.encode())
    time.sleep(2)
    engine = pyttsx3.init()
    engine.say(product['rpath'])
    engine.runAndWait()

    if not product or not product['location_image']:
        return "Location not available", 404
    return render_template('product_location.html', product=product)

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    db = get_db()
    product = db.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']

        image = product['image']
        if 'image' in request.files and request.files['image'].filename:
            img_file = request.files['image']
            image = secure_filename(img_file.filename)
            img_file.save(os.path.join(UPLOAD_FOLDER, image))

        location_image = product['location_image']
        if 'location_image' in request.files and request.files['location_image'].filename:
            loc_file = request.files['location_image']
            location_image = secure_filename(loc_file.filename)
            loc_file.save(os.path.join(LOCATION_FOLDER, location_image))

        db.execute('UPDATE products SET name=?, price=?, image=?, location_image=? WHERE id=?',
                   (name, price, image, location_image, product_id))
        db.commit()
        return redirect('/admin')

    return render_template('edit_product.html', product=product)

@app.route('/delete_product/<int:product_id>')
def delete_product(product_id):
    db = get_db()
    db.execute('DELETE FROM products WHERE id = ?', (product_id,))
    db.commit()
    return redirect('/admin')

@app.route('/clear_cart')
def clear_cart():
    session['cart'] = {}
    return redirect('/cart')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
