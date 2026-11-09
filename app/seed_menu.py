"""Creates a FRESH database with the starter menu.   Run once:  python -m app.seed_menu
WARNING: this deletes all orders and the menu. To change the menu later, use the dashboard."""
from app.db import get_db, init_db

# (name_en, name_kn, name_hi, name_ta, name_te, aliases, category, price, veg, available, description, addons)
MENU = [
    ("Masala Dosa", "ಮಸಾಲೆ ದೋಸೆ", "मसाला डोसा", "மசாலா தோசை", "మసాలా దోసె",
     "masala dose,masale dose,masala dosai,masala thosai", "Tiffin", 60, 1, 1,
     "Crispy rice crepe filled with spiced potato, served with chutney and sambar.",
     "Extra Butter:15, Extra Chutney:10, Cheese:25"),
    ("Plain Dosa", "ಸಾದಾ ದೋಸೆ", "सादा डोसा", "சாதா தோசை", "సాదా దోసె",
     "sada dosa,plain dose,plain dosai", "Tiffin", 40, 1, 1,
     "Thin crispy rice crepe with chutney and sambar.", "Extra Butter:15, Extra Chutney:10"),
    ("Set Dosa", "ಸೆಟ್ ದೋಸೆ", "सेट डोसा", "செட் தோசை", "సెట్ దోసె",
     "set dose,set dosai", "Tiffin", 55, 1, 1, "Three soft, spongy dosas served with chutney and sagu.", ""),
    ("Idli", "ಇಡ್ಲಿ", "इडली", "இட்லி", "ఇడ్లీ", "idly,iddli,idli", "Tiffin", 20, 1, 1,
     "Two steamed rice cakes with chutney and sambar. Not spicy.", "Extra Sambar:10"),
    ("Rava Idli", "ರವೆ ಇಡ್ಲಿ", "रवा इडली", "ரவா இட்லி", "రవ్వ ఇడ్లీ", "rava idly", "Tiffin", 40, 1, 1,
     "Semolina idli with cashew and curry leaves, served with chutney.", ""),
    ("Medu Vada", "ಮೆದು ವಡೆ", "मेदू वड़ा", "மெது வடை", "మెదు వడ", "vada,vade,medu vade,wada,vadai",
     "Tiffin", 30, 1, 1, "Crispy fried lentil doughnuts, served with chutney and sambar.", ""),
    ("Pongal", "ಪೊಂಗಲ್", "पोंगल", "பொங்கல்", "పొంగల్", "ven pongal", "Tiffin", 50, 1, 1,
     "Soft rice and moong dal cooked with ghee, pepper and cumin. Mild, not spicy.", "Extra Ghee:10"),
    ("Upma", "ಉಪ್ಪಿಟ್ಟು", "उपमा", "உப்புமா", "ఉప్మా", "uppittu,uppit", "Tiffin", 35, 1, 1,
     "Savoury semolina cooked with vegetables and mustard seeds.", ""),
    ("Kesari Bath", "ಕೇಸರಿ ಬಾತ್", "केसरी बाथ", "கேசரி", "కేసరి బాత్", "kesari,kesaribath", "Sweets", 40, 1, 1,
     "Sweet semolina pudding with ghee, saffron and cashews.", ""),
    ("Bisi Bele Bath", "ಬಿಸಿಬೇಳೆ ಬಾತ್", "बिसी बेले बाथ", "பிசிபேளா பாத்", "బిసిబేళే బాత్",
     "bisibele bath,bisi bele", "Meals", 70, 1, 0, "Spicy rice and lentils cooked with vegetables and tamarind.", ""),
    ("Filter Coffee", "ಫಿಲ್ಟರ್ ಕಾಫಿ", "फ़िल्टर कॉफ़ी", "ஃபில்டர் காபி", "ఫిల్టర్ కాఫీ",
     "coffee,kaapi,filter kaapi,kapi", "Drinks", 20, 1, 1, "Strong South Indian coffee with hot milk.", ""),
    ("Masala Chai", "ಮಸಾಲಾ ಚಹಾ", "मसाला चाय", "மசாலா டீ", "మసాలా టీ", "tea,chai,chaha", "Drinks", 15, 1, 1,
     "Milk tea brewed with ginger and cardamom.", ""),
]


def seed(db):
    db.executemany(
        """INSERT INTO menu_items (name_en, name_kn, name_hi, name_ta, name_te, aliases, category, price,
                                   veg, available, description, addons)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", MENU)
    db.commit()


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        init_db()
        seed(get_db())
        print(f"Seeded {len(MENU)} menu items.")
