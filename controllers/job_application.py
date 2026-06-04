from odoo import http
from odoo.http import request
from odoo.addons.website_hr_recruitment.controllers.main import WebsiteHrRecruitment
import base64
import logging

_logger = logging.getLogger(__name__)

class WebsiteHrRecruitmentCustom(WebsiteHrRecruitment):
    
    # 1. Attachment Handling (Final Version with Correct Cache Invalidation)
    def insert_attachment(self, model, id_record, files):
        """
        Override to attach files to the hr.candidate record.
        Uses invalidate_recordset() to ensure the latest data is read after creation.
        """
        
        applicant = request.env['hr.applicant'].sudo().browse(id_record)
        
        # CRITICAL FIX: This is the modern replacement for the old 'refresh()' method.
        # It marks the applicant's cache as invalid, forcing a fresh read from the 
        # database on the next field access.
        applicant.invalidate_recordset()

        # Now, when we access applicant.candidate_id, the ORM will fetch the fresh data.
        candidate = applicant.candidate_id
        if not candidate:
            _logger.error(f"Applicant {id_record} has no candidate_id after invalidation. Attaching to applicant instead.")
            # Fallback to default behavior if no candidate is found
            return super().insert_attachment(model, id_record, files)

        # --- The rest of the logic remains unchanged ---

        custom_field_names = [
            'CIN_Copy', 
            'Lettre_Motivation', 
            'Diplome_Copy', 
            'Attestations_Certificats'
        ]
        file_field_labels = {
            'CIN_Copy': "CIN (Carte d'Identité)",
            'Lettre_Motivation': 'Lettre de Motivation',
            'Diplome_Copy': 'Diplôme',
            'Attestations_Certificats': 'Attestation/Certificat',
        }
        
        custom_files_to_process = []
        for f in list(files): 
            if f.name in custom_field_names:
                custom_files_to_process.append(f)
                files.remove(f)

        orphan_attachment_ids = super().insert_attachment(model, id_record, files)
        
        for file_data in custom_files_to_process:
            field_name = file_data.name

            if not file_data or not getattr(file_data, 'filename', None):
                continue

            file_label = file_field_labels.get(field_name, field_name)

            try:
                file_content = file_data.read()
                
                if field_name == 'Attestations_Certificats':
                    attachment_name = f"{file_label} - {file_data.filename} - {candidate.name}"
                else:
                    attachment_name = f"{file_label} - {candidate.name}"

                attachment = request.env['ir.attachment'].sudo().create({
                    'name': attachment_name,
                    'datas': base64.b64encode(file_content),
                    'res_model': 'hr.candidate',   # Correct model
                    'res_id': candidate.id,        # Correct ID
                    'type': 'binary',
                })

                if attachment:
                    orphan_attachment_ids.append(attachment.id)
                    _logger.info(f"Successfully attached {field_name} to CANDIDATE {candidate.id}")

            except Exception as e:
                _logger.error(f"Error processing custom file {field_name} for candidate {candidate.id}: {str(e)}")

        return orphan_attachment_ids  
    
    # 2. Skills, Degree and Candidate Handling
    def extract_data(self, model, values):
        """
        Override extract_data to:
        1. Capture skill_ids, type_id (degree) and NEW CUSTOM FIELDS from the form.
        2. Call parent to create/link candidate.
        3. Store skills and degree temporarily to be processed after candidate creation.
        """
        
        # --- CAPTURE NEW FIELDS FOR HR.APPLICANT (don't pop them yet!) ---
        custom_applicant_fields = {}
        for field_name in ['address_domicile', 'date_opt', 'etab']:
            if field_name in values:
                # Store them temporarily
                custom_applicant_fields[field_name] = values.get(field_name)

        # 1. Capture skills and remove them from values (skills need special handling)
        skill_ids_raw = values.pop('skill_ids', None)
        skill_ids = []
        
        if skill_ids_raw:
            # Handle both comma-separated string and list formats
            if isinstance(skill_ids_raw, str):
                # Split by comma and filter out empty strings
                skill_ids = [int(x.strip()) for x in skill_ids_raw.split(',') if x.strip().isdigit()]
            elif isinstance(skill_ids_raw, list):
                skill_ids = [int(x) for x in skill_ids_raw if str(x).isdigit()]
        
        # 2. Capture degree (type_id) and remove it from values
        degree_id = values.pop('type_id', None)
        if degree_id:
            try:
                degree_id = int(degree_id)
            except (ValueError, TypeError):
                degree_id = None
                _logger.warning(f"Invalid degree_id value: {degree_id}")
        
        # 3. Call parent to get basic data and create/link candidate
        data = super().extract_data(model, values)
        
        # 4. Store skills, degree and custom fields in the data dict to process them after record creation
        if model.sudo().model == 'hr.applicant':
            # Ensure 'custom' is a dictionary
            if not isinstance(data.get('custom'), dict):
                data['custom'] = {}

            # Add skills
            if skill_ids:
                data['custom']['skill_ids'] = skill_ids
                _logger.info(f"Captured {len(skill_ids)} skills from form submission")
            
            # Add degree
            if degree_id:
                data['custom']['type_id'] = degree_id
                _logger.info(f"Captured degree type_id={degree_id} from form submission")
            
            # Add custom fields for both applicant and candidate
            if custom_applicant_fields:
                data['custom']['applicant_fields'] = custom_applicant_fields
                _logger.info(f"Captured custom fields: {list(custom_applicant_fields.keys())}")
        
        return data

    # ----------------------------------------------------------------------

    def insert_record(self, request, model, values, custom, meta=None):
        """
        Override insert_record to:
        1. Process skills and degree after the applicant is created
        2. Update custom fields on both applicant and candidate
        """
        
        # Extract skills, degree and custom fields from custom data if present
        skill_ids = custom.pop('skill_ids', []) if isinstance(custom, dict) else []
        degree_id = custom.pop('type_id', None) if isinstance(custom, dict) else None
        applicant_fields = custom.pop('applicant_fields', {}) if isinstance(custom, dict) else {}
        
        # Call parent to create the applicant record
        record_id = super().insert_record(request, model, values, custom, meta)
        
        # Now update the applicant and candidate with custom fields, skills, and degree
        if record_id and model.sudo().model == 'hr.applicant':
            try:
                applicant = request.env['hr.applicant'].sudo().browse(record_id)
                
                if applicant.exists():
                    # Update applicant with custom fields
                    if applicant_fields:
                        applicant.write(applicant_fields)
                        _logger.info(f"Updated applicant {record_id} with fields: {list(applicant_fields.keys())}")
                    
                    # Update candidate with custom fields, skills, and degree
                    if applicant.candidate_id:
                        candidate_updates = {}
                        
                        # Add custom fields to candidate
                        if applicant_fields:
                            candidate_updates.update(applicant_fields)
                        
                        # Add degree to candidate
                        if degree_id:
                            candidate_updates['type_id'] = degree_id
                        
                        # Write to candidate if there are updates
                        if candidate_updates:
                            applicant.candidate_id.write(candidate_updates)
                            _logger.info(f"Updated candidate {applicant.candidate_id.id} with fields: {list(candidate_updates.keys())}")
                        
                        # Attach skills to candidate
                        if skill_ids:
                            self._attach_skills_to_candidate(applicant.candidate_id, skill_ids)
                            _logger.info(f"Successfully attached {len(skill_ids)} skills to candidate {applicant.candidate_id.id}")
                    else:
                        _logger.warning(f"Applicant {record_id} has no candidate_id for field/skill/degree attachment")
                        
            except Exception as e:
                _logger.error(f"Error updating applicant/candidate {record_id}: {str(e)}", exc_info=True)
        
        return record_id
    
    # ----------------------------------------------------------------------

    def _attach_skills_to_candidate(self, candidate, skill_ids):
        """Helper method to attach skills to a candidate."""
        HrSkill = request.env['hr.skill'].sudo()
        HrSkillLevel = request.env['hr.skill.level'].sudo()
        
        skill_lines = []
        
        for skill_id in skill_ids:
            skill = HrSkill.browse(skill_id)
            
            if skill.exists():
                # Find the most appropriate skill level (using default_level flag)
                default_level = HrSkillLevel.search([
                    ('skill_type_id', '=', skill.skill_type_id.id)
                ], order='default_level desc, level_progress asc', limit=1)
                
                # Create the skill line command
                skill_lines.append((0, 0, {
                    'skill_id': skill_id,
                    'skill_type_id': skill.skill_type_id.id,
                    'skill_level_id': default_level.id if default_level else False,
                }))
                _logger.debug(f"Prepared skill line for skill_id={skill_id}, skill_type_id={skill.skill_type_id.id}")
            else:
                _logger.warning(f"Skill with id {skill_id} does not exist")
        
        # Write skills to the candidate
        if skill_lines:
            try:
                candidate.write({
                    'candidate_skill_ids': skill_lines
                })
                _logger.info(f"Successfully wrote {len(skill_lines)} skill lines to candidate {candidate.id}")
            except Exception as e:
                _logger.error(f"Error writing skills to candidate {candidate.id}: {str(e)}", exc_info=True)