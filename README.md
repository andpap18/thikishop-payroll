# 🚀 Deployment Οδηγίες - Streamlit Cloud (ΔΩΡΕΑΝ)

## Βήμα 1: Δημιουργία GitHub Repository

1. Πήγαινε στο https://github.com
2. Κάνε login (ή Sign Up αν δεν έχεις λογαριασμό)
3. Πάτα το **"+" → New repository**
4. Δώσε όνομα: `thikishop-payroll`
5. Επίλεξε **Public**
6. Πάτα **"Create repository"**

---

## Βήμα 2: Upload τα Αρχεία στο GitHub

### Μέθοδος A: Μέσω GitHub Web Interface (Εύκολο)

1. Στη σελίδα του repository σου, πάτα **"uploading an existing file"**
2. Drag & Drop αυτά τα 3 αρχεία από τον φάκελο `web_app`:
   - `app.py`
   - `requirements.txt`
   - `README.md` (αυτό το αρχείο)
3. Πάτα **"Commit changes"**

### Μέθοδος B: Μέσω Git (Προχωρημένο)

```bash
cd web_app
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/thikishop-payroll.git
git push -u origin main
```

---

## Βήμα 3: Deploy στο Streamlit Cloud

1. Πήγαινε στο https://share.streamlit.io
2. Κάνε **Sign in with GitHub**
3. Πάτα **"New app"**
4. Επίλεξε:
   - **Repository**: `YOUR_USERNAME/thikishop-payroll`
   - **Branch**: `main`
   - **Main file path**: `app.py`
5. Πάτα **"Deploy!"**

---

## Βήμα 4: Λήψη του URL

Μετά από ~2-3 λεπτά, το app θα είναι έτοιμο!

Θα πάρεις ένα URL όπως:
```
https://thikishop-payroll-XXXXX.streamlit.app
```

**Αυτό το URL μπορείς να το δώσεις σε όποιον θέλεις!**

---

## 🎉 Τελείωσες!

Το website είναι πλέον online και όποιος έχει το link μπορεί να το χρησιμοποιήσει!

---

## 🔄 Πώς να κάνεις Update

Αν θέλεις να κάνεις αλλαγές:

1. Άλλαξε το `app.py` στον υπολογιστή σου
2. Upload το νέο `app.py` στο GitHub (αντικατέστασε το παλιό)
3. Το Streamlit Cloud θα το ανανεώσει αυτόματα μέσα σε ~1 λεπτό!

---

## 💡 Tips

- Το app είναι **εντελώς δωρεάν** (Streamlit Cloud free tier)
- Δεν χρειάζεται server, hosting, domain - τίποτα!
- Λειτουργεί σε Windows, Mac, Linux, κινητά
- Μπορείς να το μοιραστείς με όσους θέλεις

---

## 🆘 Βοήθεια

Αν κάτι δεν δουλεύει:
- Τσέκαρε ότι τα αρχεία `app.py` και `requirements.txt` είναι στο GitHub
- Τσέκαρε το "Logs" tab στο Streamlit Cloud για λεπτομέρειες
- Βεβαιώσου ότι το repository είναι **Public**
