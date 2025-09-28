import sqlite3
import json

def update_database():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    try:
        # ตรวจสอบและเพิ่มคอลัมน์ layout_data
        c.execute("PRAGMA table_info(spaces)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'layout_data' not in columns:
            print("เพิ่มคอลัมน์ layout_data...")
            c.execute("ALTER TABLE spaces ADD COLUMN layout_data TEXT")
            
            # อัปเดตข้อมูลเก่าให้มี layout_data
            c.execute("SELECT id FROM spaces WHERE layout_data IS NULL")
            spaces = c.fetchall()
            
            for space in spaces:
                default_layout = {
                    "rows": 3,
                    "cols": 3,
                    "slots": {}
                }
                for row in range(3):
                    for col in range(3):
                        slot_id = f"{chr(65+row)}{col+1}"
                        default_layout["slots"][slot_id] = {
                            "available": True,
                            "price": 150.0
                        }
                
                c.execute("UPDATE spaces SET layout_data = ? WHERE id = ?", 
                         (json.dumps(default_layout), space[0]))
            print(f"อัปเดต layout_data สำหรับ {len(spaces)} สถานที่")
        
        # ตรวจสอบและเพิ่มคอลัมน์ slot_id
        c.execute("PRAGMA table_info(bookings)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'slot_id' not in columns:
            print("เพิ่มคอลัมน์ slot_id...")
            c.execute("ALTER TABLE bookings ADD COLUMN slot_id TEXT DEFAULT ''")
            
            # อัปเดตข้อมูลเก่าให้มี slot_id
            c.execute("UPDATE bookings SET slot_id = 'A1' WHERE slot_id = '' OR slot_id IS NULL")
            print("อัปเดต slot_id สำหรับการจองเก่า")
        
        conn.commit()
        print("✅ อัปเดต database สำเร็จ!")
        
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")
        conn.rollback()
    
    finally:
        conn.close()

if __name__ == "__main__":
    update_database()