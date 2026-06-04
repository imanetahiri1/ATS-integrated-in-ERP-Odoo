from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date


class Document(models.Model):
    _name = "softy.rec.doc"
    _description = "E-Docs"
    _rec_name = 'nom'
    _order = 'nom'

    nom = fields.Char(
        string="Nom du Document", 
        required=True,
        help="Nom du document de recrutement"
    )
    
    doc = fields.Binary(
        string="Document",
        required=True,
        help="Fichier du document de recrutement"
    )
    
    # Essential fields for better functionality
    active = fields.Boolean(
        string='Actif',
        default=True,
        help="Si décoché, le document sera archivé"
    )