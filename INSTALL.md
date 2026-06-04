# Installation de softy_recrutement

## 1. Dépendances système (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara
sudo apt-get install -y poppler-utils
```

## 2. Dépendances Python
```bash
pip3 install -r requirements.txt
```

## 3. Installation du module
1. Copier le dossier `softy_recrutement/` dans `/opt/odoo/custom_addons/`
2. Redémarrer Odoo : `sudo systemctl restart odoo`
3. Aller dans Apps → Mettre à jour la liste des applications
4. Chercher "Softy Recrutement" → Installer