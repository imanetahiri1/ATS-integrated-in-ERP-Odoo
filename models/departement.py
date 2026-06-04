# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    logo=fields.Binary(string="Logo")
    email=fields.Char(string="Email")
    # Pointage Configuration Fields
    plusieur_poitage_period = fields.Boolean(
        string="Autorisé plusieurs pointages dans une période pour un seul employé",
        default=False,
        help="Permet à un employé de faire plusieurs pointages dans la même période de travail"
    )
    
    basculer_period = fields.Boolean(
        string="Peut faire des pointages dans plusieurs périodes au même temps",
        default=False,
        help="Permet de faire des pointages dans plusieurs périodes simultanément"
    )