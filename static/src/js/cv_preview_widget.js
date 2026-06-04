/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, xml, useState, onWillStart } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class CvPreviewWidget extends Component {
    static template = xml`
        <div class="cv_preview_container" style="border: 1px solid #ddd; padding: 10px; border-radius: 5px; background: #f9f9f9; min-height: 600px;">
            <t t-if="state.fileData">
                <!-- PDF Preview -->
                <t t-if="state.isPDF">
                    <object t-att-data="state.dataUrl" 
                            type="application/pdf"
                            style="width: 100%; height: 600px; border: 1px solid #ccc;">
                        <div style="text-align: center; padding: 40px;">
                            <i class="fa fa-file-pdf-o fa-5x" style="color: #dc3545;"/>
                            <p style="margin: 20px 0;">Impossible d'afficher le PDF</p>
                            <button class="btn btn-primary" t-on-click="downloadFile">
                                <i class="fa fa-download"/> Télécharger le CV
                            </button>
                        </div>
                    </object>
                </t>
                
                <!-- Image Preview -->
                <t t-elif="state.isImage">
                    <img t-att-src="state.dataUrl" 
                         style="max-width: 100%; height: auto; border: 1px solid #ccc;"/>
                </t>
                
                <!-- WORD Preview - NOUVEAU ! -->
                <t t-elif="state.isDocx">
                    <div style="background: white; border: 1px solid #ccc; border-radius: 5px; padding: 15px;">
                        <!-- Loading -->
                        <t t-if="state.wordLoading">
                            <div style="text-align: center; padding: 40px;">
                                <i class="fa fa-spinner fa-spin fa-3x" style="color: #2b5797;"/>
                                <p style="margin: 20px 0;">Conversion du document Word...</p>
                            </div>
                        </t>
                        
                        <!-- Erreur conversion -->
                        <t t-elif="state.wordError">
                            <div style="text-align: center; padding: 40px;">
                                <i class="fa fa-file-word-o fa-5x" style="color: #dc3545;"/>
                                <p style="margin: 20px 0; color: #dc3545;">
                                    Erreur de conversion : <t t-esc="state.wordError"/>
                                </p>
                                <button class="btn btn-primary" t-on-click="downloadFile">
                                    <i class="fa fa-download"/> Télécharger le CV
                                </button>
                            </div>
                        </t>
                        
                        <!-- Aperçu Word converti -->
                        <t t-elif="state.wordHtml">
                            <div style="margin-bottom: 10px; padding: 10px; background: #e3f2fd; border-left: 3px solid #2b5797;">
                                <i class="fa fa-file-word-o"/> 
                                <strong>Document Word</strong> - Aperçu HTML
                                <button class="btn btn-sm btn-primary" 
                                        t-on-click="downloadFile"
                                        style="float: right;">
                                    <i class="fa fa-download"/> Télécharger
                                </button>
                            </div>
                            <div style="max-height: 550px; overflow-y: auto; padding: 15px; background: white;">
                                <div t-out="state.wordHtml" 
                                     style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; line-height: 1.6;"/>
                            </div>
                        </t>
                    </div>
                </t>
                
                <!-- Autres formats -->
                <t t-else="">
                    <div style="text-align: center; padding: 40px;">
                        <i class="fa fa-file-o fa-5x" style="color: #999;"/>
                        <p style="margin: 20px 0;">Aperçu non disponible</p>
                        <button class="btn btn-primary" t-on-click="downloadFile">
                            <i class="fa fa-download"/> Télécharger
                        </button>
                    </div>
                </t>
            </t>
            <t t-else="">
                <div style="text-align: center; padding: 40px; color: #999;">
                    <i class="fa fa-file-o fa-5x"/>
                    <p style="margin: 20px 0;">Aucun CV attaché</p>
                </div>
            </t>
        </div>
    `;

    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState(this.getFileInfo());
        
        // Si c'est un Word, convertir au chargement
        if (this.state.isDocx && this.state.fileData) {
            onWillStart(async () => {
                await this.convertWordToHtml();
            });
        }
    }

    getFileInfo() {
        const fileData = this.props.record.data.cv_file;
        const filename = this.props.record.data.cv_filename || "";
        
        if (!fileData) {
            return { fileData: null };
        }

        const ext = filename.toLowerCase().split('.').pop();
        const isPDF = ext === 'pdf';
        const isDocx = ['docx', 'doc'].includes(ext);
        const isImage = ['jpg', 'jpeg', 'png', 'gif'].includes(ext);
        
        let dataUrl = `data:application/octet-stream;base64,${fileData}`;
        
        if (isPDF) {
            dataUrl = `data:application/pdf;base64,${fileData}`;
        } else if (isImage) {
            dataUrl = `data:image/${ext};base64,${fileData}`;
        }

        return { 
            fileData, 
            filename, 
            isPDF, 
            isDocx, 
            isImage, 
            dataUrl,
            wordLoading: isDocx ? true : false,
            wordHtml: null,
            wordError: null
        };
    }

    async convertWordToHtml() {
        this.state.wordLoading = true;
        this.state.wordError = null;

        try {
            // Charger Mammoth.js si pas déjà chargé
            if (!window.mammoth) {
                await this.loadMammothLib();
            }

            // Convertir base64 en ArrayBuffer
            const binaryString = atob(this.state.fileData);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            // Convertir avec Mammoth
            const result = await window.mammoth.convertToHtml(
                { arrayBuffer: bytes.buffer },
                {
                    styleMap: [
                        "p[style-name='Heading 1'] => h1:fresh",
                        "p[style-name='Heading 2'] => h2:fresh",
                        "p[style-name='Heading 3'] => h3:fresh",
                        "b => strong",
                        "i => em",
                    ]
                }
            );

            this.state.wordHtml = result.value;
            
            if (result.messages && result.messages.length > 0) {
                console.warn("Mammoth conversion warnings:", result.messages);
            }

        } catch (error) {
            console.error("Erreur conversion Word:", error);
            this.state.wordError = error.message || "Conversion impossible";
        } finally {
            this.state.wordLoading = false;
        }
    }

    loadMammothLib() {
        return new Promise((resolve, reject) => {
            // Vérifier si déjà chargé
            if (window.mammoth) {
                resolve();
                return;
            }

            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.6.0/mammoth.browser.min.js';
            script.onload = () => resolve();
            script.onerror = () => reject(new Error('Impossible de charger Mammoth.js'));
            document.head.appendChild(script);
        });
    }

    downloadFile() {
        const link = document.createElement('a');
        link.href = this.state.dataUrl;
        link.download = this.state.filename;
        link.click();
    }
}

registry.category("fields").add("cv_preview", {
    component: CvPreviewWidget,
});