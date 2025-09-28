import sqlite3
import json

def check_database():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    print("=== ตรวจสอบ Schema ===")
    
    # ตรวจสอบตาราง spaces
    print("\n1. ตาราง spaces:")
    c.execute("PRAGMA table_info(spaces)")
    for column in c.fetchall():
        print(f"   - {column[1]} ({column[2]})")
    
    # ตรวจสอบตาราง bookings
    print("\n2. ตาราง bookings:")
    c.execute("PRAGMA table_info(bookings)")
    for column in c.fetchall():
        print(f"   - {column[1]} ({column[2]})")
    
    # ตรวจสอบข้อมูลตัวอย่าง
    print("\n3. ข้อมูลสถานที่:")
    c.execute("SELECT id, name, layout_data FROM spaces LIMIT 3")
    spaces = c.fetchall()
    for space in spaces:
        print(f"   - {space[1]}")
        if space[2]:
            layout = json.loads(space[2])
            print(f"     Layout: {layout['rows']}x{layout['cols']}")
        else:
            print("     Layout: ไม่มีข้อมูล")
    
    print("\n4. ข้อมูลการจอง:")
    c.execute("SELECT COUNT(*) FROM bookings")
    booking_count = c.fetchone()[0]
    print(f"   - จำนวนการจอง: {booking_count}")
    
    if booking_count > 0:
        c.execute("SELECT slot_id FROM bookings WHERE slot_id IS NOT NULL AND slot_id != '' LIMIT 5")
        slots = c.fetchall()
        print(f"   - ตัวอย่าง slot_id: {[slot[0] for slot in slots]}")
    
    conn.close()
    print("\n✅ ตรวจสอบเสร็จสิ้น!")

if __name__ == "__main__":
    check_database()