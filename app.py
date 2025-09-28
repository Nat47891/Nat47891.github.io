from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import hashlib
from datetime import datetime
import qrcode
import io
import base64
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# สร้างฐานข้อมูล
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # ตารางผู้ใช้
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  first_name TEXT NOT NULL,
                  last_name TEXT NOT NULL,
                  phone TEXT NOT NULL UNIQUE,
                  password TEXT NOT NULL,
                  user_type TEXT DEFAULT 'customer')''')
    
    # ตารางสถานที่ (เพิ่ม layout_data)
    c.execute('''CREATE TABLE IF NOT EXISTS spaces
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  location TEXT NOT NULL,
                  size TEXT NOT NULL,
                  price REAL NOT NULL,
                  available_days TEXT NOT NULL,
                  available_time TEXT NOT NULL,
                  amenities TEXT,
                  owner_id INTEGER,
                  layout_data TEXT,
                  FOREIGN KEY (owner_id) REFERENCES users (id))''')
    
    # ตารางการจอง (เพิ่ม slot_id)
    c.execute('''CREATE TABLE IF NOT EXISTS bookings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  space_id INTEGER,
                  booking_date TEXT NOT NULL,
                  slot_id TEXT NOT NULL,
                  status TEXT DEFAULT 'pending',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users (id),
                  FOREIGN KEY (space_id) REFERENCES spaces (id))''')
    
    # ตรวจสอบว่าคอลัมน์ layout_data และ slot_id มีอยู่แล้วหรือไม่
    c.execute("PRAGMA table_info(spaces)")
    columns = [column[1] for column in c.fetchall()]
    if 'layout_data' not in columns:
        c.execute("ALTER TABLE spaces ADD COLUMN layout_data TEXT")
    
    c.execute("PRAGMA table_info(bookings)")
    columns = [column[1] for column in c.fetchall()]
    if 'slot_id' not in columns:
        c.execute("ALTER TABLE bookings ADD COLUMN slot_id TEXT DEFAULT ''")
    
    # เพิ่มข้อมูลตัวอย่าง
    c.execute("SELECT COUNT(*) FROM spaces")
    if c.fetchone()[0] == 0:
        # สร้าง layout ตัวอย่าง (ตาราง 5x5)
        sample_layout = {
            "rows": 5,
            "cols": 5,
            "slots": {}
        }
        for row in range(5):
            for col in range(5):
                slot_id = f"{chr(65+row)}{col+1}"  # A1, A2, B1, B2, etc.
                sample_layout["slots"][slot_id] = {
                    "available": True,
                    "price": 150.0
                }
        
        sample_spaces = [
            ('ตลาดเช้าวังทองหลาง', 'วังทองหลาง กรุงเทพฯ', '5x5 ล็อค', 150.0, 'จันทร์,พุธ,ศุกร์', '05:00-12:00', 'ไฟฟ้า, น้ำประปา, ที่จอดรถ', None, json.dumps(sample_layout)),
            ('ตลาดเย็นลาดพร้าว', 'ลาดพร้าว กรุงเทพฯ', '4x6 ล็อค', 200.0, 'ทุกวัน', '16:00-22:00', 'ไฟฟ้า, ระบายอากาศดี', None, json.dumps({
                "rows": 4, "cols": 6, "slots": {
                    f"{chr(65+row)}{col+1}": {"available": True, "price": 200.0}
                    for row in range(4) for col in range(6)
                }
            })),
        ]
        c.executemany("INSERT INTO spaces (name, location, size, price, available_days, available_time, amenities, owner_id, layout_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", sample_spaces)
    
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return base64.b64encode(buffer.getvalue()).decode()

@app.route('/')
def index():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    search = request.args.get('search', '')
    location_filter = request.args.get('location', '')
    
    query = "SELECT * FROM spaces WHERE 1=1"
    params = []
    
    if search:
        query += " AND (name LIKE ? OR location LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    if location_filter:
        query += " AND location LIKE ?"
        params.append(f'%{location_filter}%')
    
    c.execute(query, params)
    spaces = c.fetchall()
    conn.close()
    
    return render_template('index.html', spaces=spaces)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form['phone']
        password = request.form['password']
        user_type = request.form.get('user_type', 'customer')
        
        hashed_password = hash_password(password)
        
        try:
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (first_name, last_name, phone, password, user_type) VALUES (?, ?, ?, ?, ?)",
                     (first_name, last_name, phone, hashed_password, user_type))
            conn.commit()
            conn.close()
            
            flash('สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('เบอร์โทรศัพท์นี้ถูกใช้งานแล้ว', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']
        password = request.form['password']
        hashed_password = hash_password(password)
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE phone = ? AND password = ?", (phone, hashed_password))
        user = c.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['user_name'] = f"{user[1]} {user[2]}"
            session['user_type'] = user[5]
            flash('เข้าสู่ระบบสำเร็จ!', 'success')
            return redirect(url_for('index'))
        else:
            flash('เบอร์โทรหรือรหัสผ่านไม่ถูกต้อง', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('ออกจากระบบแล้ว', 'info')
    return redirect(url_for('index'))

@app.route('/booking/<int:space_id>')
def booking(space_id):
    if 'user_id' not in session:
        flash('กรุณาเข้าสู่ระบบก่อน', 'error')
        return redirect(url_for('login'))
    
    booking_date = request.args.get('date', '')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM spaces WHERE id = ?", (space_id,))
    space = c.fetchone()
    
    if not space:
        flash('ไม่พบสถานที่นี้', 'error')
        return redirect(url_for('index'))
    
    # ดึงข้อมูลการจองที่มีอยู่แล้วในวันที่เลือก
    booked_slots = []
    if booking_date:
        c.execute("""SELECT slot_id, u.first_name, u.last_name 
                     FROM bookings b 
                     JOIN users u ON b.user_id = u.id 
                     WHERE b.space_id = ? AND b.booking_date = ? AND b.status != 'cancelled'""", 
                  (space_id, booking_date))
        booked_data = c.fetchall()
        booked_slots = {row[0]: f"{row[1]} {row[2]}" for row in booked_data}
    
    conn.close()
    
    # Parse layout data
    layout_data = json.loads(space[9]) if space[9] else {"rows": 3, "cols": 3, "slots": {}}
    
    return render_template('booking.html', space=space, layout_data=layout_data, 
                         booked_slots=booked_slots, booking_date=booking_date)

@app.route('/get_booking_data/<int:space_id>')
def get_booking_data(space_id):
    booking_date = request.args.get('date', '')
    
    if not booking_date:
        return jsonify({"booked_slots": {}})
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""SELECT slot_id, u.first_name, u.last_name 
                 FROM bookings b 
                 JOIN users u ON b.user_id = u.id 
                 WHERE b.space_id = ? AND b.booking_date = ? AND b.status != 'cancelled'""", 
              (space_id, booking_date))
    booked_data = c.fetchall()
    conn.close()
    
    booked_slots = {row[0]: f"{row[1]} {row[2]}" for row in booked_data}
    
    return jsonify({"booked_slots": booked_slots})

@app.route('/confirm_booking', methods=['POST'])
def confirm_booking():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    space_id = request.form['space_id']
    booking_date = request.form['booking_date']
    selected_slots = request.form.getlist('selected_slots')
    
    if not selected_slots:
        flash('กรุณาเลือกล็อคที่ต้องการจอง', 'error')
        return redirect(url_for('booking', space_id=space_id) + f'?date={booking_date}')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # ตรวจสอบว่าล็อคที่เลือกว่างหรือไม่
    for slot_id in selected_slots:
        c.execute("SELECT * FROM bookings WHERE space_id = ? AND booking_date = ? AND slot_id = ? AND status != 'cancelled'", 
                  (space_id, booking_date, slot_id))
        existing_booking = c.fetchone()
        
        if existing_booking:
            flash(f'ล็อค {slot_id} ถูกจองแล้ว กรุณาเลือกล็อคอื่น', 'error')
            return redirect(url_for('booking', space_id=space_id) + f'?date={booking_date}')
    
    # สร้างการจองสำหรับแต่ละล็อค
    booking_ids = []
    total_price = 0
    
    for slot_id in selected_slots:
        c.execute("INSERT INTO bookings (user_id, space_id, booking_date, slot_id) VALUES (?, ?, ?, ?)",
                  (session['user_id'], space_id, booking_date, slot_id))
        booking_ids.append(c.lastrowid)
    
    # ดึงข้อมูลสถานที่และคำนวณราคา
    c.execute("SELECT * FROM spaces WHERE id = ?", (space_id,))
    space = c.fetchone()
    
    layout_data = json.loads(space[9]) if space[9] else {}
    for slot_id in selected_slots:
        slot_price = layout_data.get("slots", {}).get(slot_id, {}).get("price", space[4])
        total_price += slot_price
    
    conn.commit()
    conn.close()
    
    # สร้าง QR Code สำหรับชำระเงิน
    payment_data = f"BOOKING:{','.join(map(str, booking_ids))}:AMOUNT:{total_price}:SPACE:{space[1]}:SLOTS:{','.join(selected_slots)}"
    qr_code = generate_qr_code(payment_data)
    
    return render_template('payment.html', 
                         booking_ids=booking_ids,
                         selected_slots=selected_slots,
                         space=space, 
                         booking_date=booking_date,
                         total_price=total_price,
                         qr_code=qr_code)

@app.route('/confirm_payment', methods=['POST'])
def confirm_payment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    booking_ids = request.form.getlist('booking_ids')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    for booking_id in booking_ids:
        c.execute("UPDATE bookings SET status = 'confirmed' WHERE id = ? AND user_id = ?", 
                  (booking_id, session['user_id']))
    
    conn.commit()
    conn.close()
    
    flash('ชำระเงินสำเร็จ! การจองของคุณได้รับการยืนยันแล้ว', 'success')
    return redirect(url_for('my_bookings'))

@app.route('/my_bookings')
def my_bookings():
    if 'user_id' not in session:
        flash('กรุณาเข้าสู่ระบบก่อน', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""SELECT b.*, s.name, s.location, s.size, s.price, u.first_name, u.last_name, u.phone
                 FROM bookings b 
                 JOIN spaces s ON b.space_id = s.id 
                 JOIN users u ON b.user_id = u.id
                 WHERE b.user_id = ?
                 ORDER BY b.created_at DESC""", (session['user_id'],))
    bookings = c.fetchall()
    conn.close()
    
    return render_template('my_bookings.html', bookings=bookings)

@app.route('/manage_spaces')
def manage_spaces():
    if 'user_id' not in session:
        flash('กรุณาเข้าสู่ระบบก่อน', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # ดูสถานที่ทั้งหมด (สำหรับ admin) หรือสถานที่ของตัวเอง
    if session.get('user_type') == 'admin':
        c.execute("SELECT * FROM spaces")
    else:
        c.execute("SELECT * FROM spaces WHERE owner_id = ? OR owner_id IS NULL", (session['user_id'],))
    
    spaces = c.fetchall()
    conn.close()
    
    return render_template('manage_spaces.html', spaces=spaces)

@app.route('/add_space', methods=['POST'])
def add_space():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        name = request.form['name']
        location = request.form['location']
        rows = int(request.form['rows'])
        cols = int(request.form['cols'])
        price = float(request.form['price'])
        available_days = request.form['available_days']
        available_time = request.form['available_time']
        amenities = request.form['amenities']
        
        # สร้าง layout data
        layout_data = {
            "rows": rows,
            "cols": cols,
            "slots": {}
        }
        
        for row in range(rows):
            for col in range(cols):
                slot_id = f"{chr(65+row)}{col+1}"  # A1, A2, B1, B2, etc.
                layout_data["slots"][slot_id] = {
                    "available": True,
                    "price": price
                }
        
        size = f"{rows}x{cols} ล็อค"
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("""INSERT INTO spaces (name, location, size, price, available_days, available_time, amenities, owner_id, layout_data) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (name, location, size, price, available_days, available_time, amenities, session['user_id'], json.dumps(layout_data)))
        conn.commit()
        conn.close()
        
        flash('เพิ่มสถานที่สำเร็จ!', 'success')
        
    except Exception as e:
        flash(f'เกิดข้อผิดพลาด: {str(e)}', 'error')
    
    return redirect(url_for('manage_spaces'))

@app.route('/edit_space/<int:space_id>')
def edit_space(space_id):
    if 'user_id' not in session:
        flash('กรุณาเข้าสู่ระบบก่อน', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM spaces WHERE id = ? AND (owner_id = ? OR ? = 'admin')", 
              (space_id, session['user_id'], session.get('user_type', '')))
    space = c.fetchone()
    conn.close()
    
    if not space:
        flash('ไม่พบสถานที่หรือคุณไม่มีสิทธิ์แก้ไข', 'error')
        return redirect(url_for('manage_spaces'))
    
    layout_data = json.loads(space[9]) if space[9] else {"rows": 3, "cols": 3, "slots": {}}
    
    return render_template('edit_space.html', space=space, layout_data=layout_data)

@app.route('/update_space/<int:space_id>', methods=['POST'])
def update_space(space_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        name = request.form['name']
        location = request.form['location']
        rows = int(request.form['rows'])
        cols = int(request.form['cols'])
        price = float(request.form['price'])
        available_days = request.form['available_days']
        available_time = request.form['available_time']
        amenities = request.form['amenities']
        
        # อัปเดต layout data
        layout_data = {
            "rows": rows,
            "cols": cols,
            "slots": {}
        }
        
        for row in range(rows):
            for col in range(cols):
                slot_id = f"{chr(65+row)}{col+1}"
                layout_data["slots"][slot_id] = {
                    "available": True,
                    "price": price
                }
        
        size = f"{rows}x{cols} ล็อค"
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("""UPDATE spaces SET name = ?, location = ?, size = ?, price = ?, 
                     available_days = ?, available_time = ?, amenities = ?, layout_data = ?
                     WHERE id = ? AND (owner_id = ? OR ? = 'admin')""",
                  (name, location, size, price, available_days, available_time, amenities, 
                   json.dumps(layout_data), space_id, session['user_id'], session.get('user_type', '')))
        
        if c.rowcount > 0:
            flash('แก้ไขสถานที่สำเร็จ!', 'success')
        else:
            flash('ไม่สามารถแก้ไขได้', 'error')
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        flash(f'เกิดข้อผิดพลาด: {str(e)}', 'error')
    
    return redirect(url_for('manage_spaces'))

@app.route('/delete_space/<int:space_id>')
def delete_space(space_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # ตรวจสอบว่ามีการจองอยู่หรือไม่
    c.execute("SELECT COUNT(*) FROM bookings WHERE space_id = ? AND status = 'confirmed'", (space_id,))
    booking_count = c.fetchone()[0]
    
    if booking_count > 0:
        flash('ไม่สามารถลบได้ เนื่องจากมีการจองที่ยืนยันแล้ว', 'error')
    else:
        c.execute("DELETE FROM spaces WHERE id = ? AND (owner_id = ? OR ? = 'admin')", 
                  (space_id, session['user_id'], session.get('user_type', '')))
        
        if c.rowcount > 0:
            # ลบการจองที่ยังไม่ยืนยัน
            c.execute("DELETE FROM bookings WHERE space_id = ? AND status = 'pending'", (space_id,))
            flash('ลบสถานที่สำเร็จ!', 'success')
        else:
            flash('ไม่สามารถลบได้', 'error')
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('manage_spaces'))

@app.route('/cancel_booking/<int:booking_id>')
def cancel_booking(booking_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ? AND user_id = ? AND status = 'pending'", 
              (booking_id, session['user_id']))
    
    if c.rowcount > 0:
        flash('ยกเลิกการจองสำเร็จ!', 'success')
    else:
        flash('ไม่สามารถยกเลิกได้', 'error')
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('my_bookings'))

@app.route('/view_space_bookings/<int:space_id>')
def view_space_bookings(space_id):
    if 'user_id' not in session:
        flash('กรุณาเข้าสู่ระบบก่อน', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # ดึงข้อมูลสถานที่
    c.execute("SELECT * FROM spaces WHERE id = ? AND (owner_id = ? OR ? = 'admin')", 
              (space_id, session['user_id'], session.get('user_type', '')))
    space = c.fetchone()
    
    if not space:
        flash('ไม่พบสถานที่หรือคุณไม่มีสิทธิ์เข้าถึง', 'error')
        return redirect(url_for('manage_spaces'))
    
    # ดึงข้อมูลการจองทั้งหมด
    c.execute("""SELECT b.*, u.first_name, u.last_name, u.phone
                 FROM bookings b 
                 JOIN users u ON b.user_id = u.id
                 WHERE b.space_id = ?
                 ORDER BY b.booking_date DESC, b.slot_id""", (space_id,))
    bookings = c.fetchall()
    
    conn.close()
    
    layout_data = json.loads(space[9]) if space[9] else {"rows": 3, "cols": 3, "slots": {}}
    
    return render_template('view_space_bookings.html', space=space, bookings=bookings, layout_data=layout_data)

@app.route('/cancel_space_bookings', methods=['POST'])
def cancel_space_bookings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    space_id = request.form['space_id']
    booking_date = request.form['booking_date']
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # ยกเลิกการจองทั้งหมดในวันที่และสถานที่นั้น
    c.execute("""UPDATE bookings SET status = 'cancelled' 
                 WHERE space_id = ? AND booking_date = ? AND user_id = ? AND status = 'pending'""", 
              (space_id, booking_date, session['user_id']))
    
    if c.rowcount > 0:
        flash(f'ยกเลิกการจองทั้งหมดในวันที่ {booking_date} สำเร็จ!', 'success')
    else:
        flash('ไม่สามารถยกเลิกได้', 'error')
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('my_bookings'))

# เพิ่ม template filter
@app.template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value) if value else {}
    except:
        return {}

@app.template_filter('chr')
def chr_filter(value):
    return chr(int(value))

if __name__ == '__main__':
    init_db()
    app.run()