from app import create_app
from app.db import get_db, init_db

# (name_en, name_kn, name_hi, aliases, category, price, veg, available)
MENU = [
    ("Masala Dosa", "ಮಸಾಲೆ ದೋಸೆ", "मसाला डोसा", "masala dose,masale dose,masala dosai", "Tiffin", 60, 1, 1),
    ("Plain Dosa", "ಸಾದಾ ದೋಸೆ", "सादा डोसा", "sada dosa,plain dose", "Tiffin", 40, 1, 1),
    ("Set Dosa", "ಸೆಟ್ ದೋಸೆ", "सेट डोसा", "set dose", "Tiffin", 55, 1, 1),
    ("Idli", "ಇಡ್ಲಿ", "इडली", "idly,iddli,idli", "Tiffin", 20, 1, 1),
    ("Rava Idli", "ರವೆ ಇಡ್ಲಿ", "रवा इडली", "rava idly", "Tiffin", 40, 1, 1),
    ("Medu Vada", "ಮೆದು ವಡೆ", "मेदू वड़ा", "vada,vade,medu vade,wada", "Tiffin", 30, 1, 1),
    ("Pongal", "ಪೊಂಗಲ್", "पोंगल", "ven pongal", "Tiffin", 50, 1, 1),
    ("Upma", "ಉಪ್ಪಿಟ್ಟು", "उपमा", "uppittu,uppit", "Tiffin", 35, 1, 1),
    ("Kesari Bath", "ಕೇಸರಿ ಬಾತ್", "केसरी बाथ", "kesari,kesaribath", "Sweets", 40, 1, 1),
    ("Bisi Bele Bath", "ಬಿಸಿಬೇಳೆ ಬಾತ್", "बिसी बेले बाथ", "bisibele bath,bisi bele", "Meals", 70, 1, 0),
    ("Filter Coffee", "ಫಿಲ್ಟರ್ ಕಾಫಿ", "फ़िल्टर कॉफ़ी", "coffee,kaapi,filter kaapi", "Drinks", 20, 1, 1),
    ("Masala Chai", "ಮಸಾಲಾ ಚಹಾ", "मसाला चाय", "tea,chai,chaha", "Drinks", 15, 1, 1),
]

app = create_app()
with app.app_context():
    init_db()
    db = get_db()
    db.executemany(
        """INSERT INTO menu_items
           (name_en, name_kn, name_hi, aliases, category, price, veg, available)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        MENU,
    )
    db.commit()
    print(f"Seeded {len(MENU)} menu items.")