import xml.etree.ElementTree as ET
from fpdf import FPDF
import os

class FacturaXMLtoPDF:
    def __init__(self, xml_path, output_path):
        self.xml_path = xml_path
        self.output_path = output_path
        self.data = {}
        self.line_height = 4
        self.page_width = 80  # Ancho para impresora de 80mm
        
    def parse_xml(self):
        """Parsear el archivo XML de la factura"""
        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()
            
            # Namespaces comunes en facturas electrónicas
            namespaces = {
                'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
                'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
            }

            # Inicializar datos
            self.data['monto_letras'] = ''
            self.data['forma_pago'] = ''
            self.data['otras_notes'] = []
            
            # Extraer todos los notes
            notes = root.findall('.//cbc:Note', namespaces)
            for note in notes:
                note_text = note.text or ''
                language_locale = note.get('languageLocaleID')
                language_id = note.get('languageID')
                
                if language_locale == "1000":
                    self.data['monto_letras'] = note_text
                elif language_id == "L":
                    self.data['forma_pago'] = note_text
                else:
                    # Guardar notes no identificados
                    self.data['otras_notes'].append({
                        'texto': note_text,
                        'languageLocaleID': language_locale,
                        'languageID': language_id
                    })

        
            # Extraer datos básicos
            self.data['numero_factura'] = self.get_text(root, './/cbc:ID', namespaces)
            self.data['fecha_emision'] = self.get_text(root, './/cbc:IssueDate', namespaces)
            self.data['hora_emision'] = self.get_text(root, './/cbc:IssueTime', namespaces)
            
            # DETECTAR TIPO DE DOCUMENTO AUTOMÁTICAMENTE
            numero = self.data.get('numero_factura', '')
            if numero and numero[0].upper() == 'F':
                self.data['tipo_documento'] = "FACTURA"
            else:
                self.data['tipo_documento'] = "BOLETA DE VENTA"
            
            # Datos del emisor
            emisor = root.find('.//cac:AccountingSupplierParty/cac:Party', namespaces)
            if emisor is not None:
                self.data['emisor_nombre'] = self.get_text(emisor, './/cbc:Name', namespaces)
                self.data['emisor_ruc'] = self.get_text(emisor, './/cbc:ID', namespaces)
                self.data['emisor_direccion'] = self.get_text(emisor, './/cac:AddressLine/cbc:Line', namespaces)
                self.data['emisor_distrito'] = self.get_text(emisor, './/cbc:District', namespaces)
                self.data['emisor_departamento'] = self.get_text(emisor, './/cbc:CityName', namespaces)
            
            # Datos del cliente
            cliente = root.find('.//cac:AccountingCustomerParty/cac:Party', namespaces)
            if cliente is not None:
                self.data['cliente_nombre'] = self.get_text(cliente, './/cbc:RegistrationName', namespaces)
                self.data['cliente_ID'] = self.get_text(cliente, './/cbc:ID', namespaces)
                self.data['cliente_direccion'] = self.get_text(cliente, './/cac:AddressLine/cbc:Line', namespaces)
                self.data['cliente_distrito'] = self.get_text(cliente, './/cbc:District', namespaces)
                self.data['cliente_departamento'] = self.get_text(cliente, './/cbc:CityName', namespaces)
            
            # Totales
            self.data['total_venta'] = self.get_text(root, './/cac:TaxSubtotal/cbc:TaxableAmount', namespaces, '0.00')
            self.data['total_igv'] = self.get_text(root, './/cac:TaxTotal/cbc:TaxAmount', namespaces, '0.00')
            self.data['total_pagar'] = self.get_text(root, './/cac:LegalMonetaryTotal/cbc:PayableAmount', namespaces, '0.00')
            
            # Items de la factura
            self.data['items'] = []
            for item in root.findall('.//cac:InvoiceLine', namespaces):
                item_data = {}
                item_data['id'] = self.get_text(item, './/cac:SellersItemIdentification/cbc:ID', namespaces)
                item_data['unidad'] = self.get_text(item, './/cbc:Note', namespaces)
                item_data['descripcion'] = self.get_text(item, './/cbc:Description', namespaces)
                item_data['cantidad'] = self.get_text(item, './/cbc:InvoicedQuantity', namespaces, '0')
                item_data['precio_unitario'] = self.get_text(item, './/cac:Price/cbc:PriceAmount', namespaces, '0.00')
                item_data['total'] = self.get_text(item, './/cbc:LineExtensionAmount', namespaces, '0.00')
                
                self.data['items'].append(item_data)
                
            return True
            
        except Exception as e:
            print(f"Error al parsear XML: {e}")
            return False
    
    def get_text(self, element, xpath, namespaces, default='N/A'):
        """Helper para obtener texto de elementos XML de forma segura"""
        result = element.find(xpath, namespaces)
        return result.text if result is not None else default
    
    def format_currency(self, amount):
        """Formatear montos monetarios"""
        try:
            return f"S/. {float(amount):.2f}"
        except:
            return f"S/. 0.00"
        
    def calcular_lineas_texto(self, texto, ancho_maximo, font_size=6):
        #"""Calcular cuántas líneas ocupa un texto"""
        if not texto:
            return 1
        # Aproximación simple para font size 6
        caracteres_por_linea = int(ancho_maximo * 2.2)
        return max(1, (len(texto) // caracteres_por_linea) + 1)
    
    def calculate_total_height(self):
        #"""Calcular la altura total necesaria para el PDF basado en el contenido real"""
        # Altura de secciones fijas
        altura = 100  # Encabezado, emisor, cliente, totales, separadores
    
        # Altura de la imagen si existe
        try:
            if os.path.exists("images/logo_manchester.png"):
                altura += 25
        except:
            pass
        
        # Altura de los items
        for item in self.data.get('items', []):
            descripcion = str(item.get('descripcion', ''))
            # Calcular líneas de descripción (aproximadamente 20 caracteres por línea)
            lineas = max(1, (len(descripcion) // 20) + 1)
            altura_item = lineas * 4  # 4mm por línea
            altura += altura_item
        
        # Textos multilínea adicionales
        textos_largos = [
            self.data.get('emisor_nombre', ''),
            self.data.get('cliente_nombre', ''),
            self.data.get('monto_letras', '')
        ]
        
        for texto in textos_largos:
            if texto and len(texto) > 35:
                altura += 4  # línea adicional
        
        # Mínimo 150mm, máximo 800mm
        return max(150, min(800, altura))


    def generate_pdf(self):
        """Generar PDF para impresora de 80mm con alto automático"""
        # Calcular alto automático
        page_height = self.calculate_total_height()
        
        # Crear PDF con márgenes mínimos
        pdf = FPDF(orientation='P', unit='mm', format=(self.page_width, page_height))
        pdf.set_margins(left=2, top=2, right=2)  # Márgenes mínimos
        pdf.set_auto_page_break(auto=False)  # Desactivar auto page break
        
        pdf.add_page()
    
        # AGREGAR IMAGEN EN EL ENCABEZADO CON MÁS OPCIONES
        image_path = "images/logo_manchester.png"
        image_x = 10  # Posición X (centrada para 80mm: (80-60)/2 = 10)
        image_y = 5   # Posición Y desde arriba
        image_width = 60  # Ancho de la imagen (60mm para dejar márgenes)
        
        try:
            if os.path.exists(image_path):
                # Insertar imagen centrada
                pdf.image(image_path, x=image_x, y=image_y, w=image_width)
                
                # Calcular altura de la imagen para ajustar el espacio
                # (asumiendo relación de aspecto 3:1 para logos)
                image_height = image_width / 3
                pdf.ln(image_height + 2)  # Espacio después de la imagen
            else:
                print(f"Advertencia: No se encontró {image_path}")
                # Crear directorio si no existe
                os.makedirs("images", exist_ok=True)
                pdf.ln(5)
        except Exception as e:
            print(f"Error al cargar imagen {image_path}: {e}")
        pdf.ln(5)  # Espacio normal si no hay imagen
        
        # Configuración de fuentes
        pdf.set_font("Arial", '', 8)

        # Emisor nombre (centrado)
        emisor_nombre = self.data.get('emisor_nombre', 'N/A')
        if len(emisor_nombre) > 35:
            pdf.multi_cell(0, 4, emisor_nombre, 0, 'C')
        else:
            pdf.cell(0, 4, emisor_nombre, 0, 1, 'C')

        # RUC (centrado, sin texto "RUC:")
        pdf.cell(0, 4, self.data.get('emisor_ruc', 'N/A'), 0, 1, 'C')

        # Dirección completa (centrada, sin texto "Dirección:")
        emisor_dir = self.data.get('emisor_direccion', '')
        emisor_dis = self.data.get('emisor_distrito', '')
        emisor_dep = self.data.get('emisor_departamento', '')

        # Formatear la dirección correctamente
        direccion_completa = f"{emisor_dir}"
        if emisor_dis:
            direccion_completa += f" - {emisor_dis}"
        if emisor_dep:
            direccion_completa += f" - {emisor_dep}"

        if len(direccion_completa) > 35:
            pdf.multi_cell(0, 4, direccion_completa, 0, 'C')
        else:
            pdf.cell(0, 4, direccion_completa, 0, 1, 'C')

        pdf.ln(2)
        
        # Línea separadora
        pdf.cell(0, 1, "", "T", 1)
        pdf.ln(2)

        # Encabezado - CENTRADO
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 5, f"{self.data.get('tipo_documento', 'COMPROBANTE')} ELECTRÓNICA", 0, 1, 'C')
        pdf.set_font("Arial", '', 8)
        pdf.cell(0, 4, f"NRO. {self.data.get('numero_factura', 'N/A')}", 0, 1, 'C')
        pdf.ln(2)

        # Línea separadora
        pdf.cell(0, 1, "", "T", 1)
        pdf.ln(2)
        
        # Información del cliente
        pdf.set_font("Arial", '', 8)
        # Obtener el ID del cliente
        cliente_id = self.data.get('cliente_ID', '')

        # Determinar el tipo de documento según la longitud
        if len(cliente_id) == 11:  # RUC tiene 11 dígitos
            pdf.cell(0, 4, f"RUC: {cliente_id}", 0, 1)
        elif len(cliente_id) == 8:  # DNI tiene 8 dígitos
            pdf.cell(0, 4, f"DNI: {cliente_id}", 0, 1)
        elif cliente_id:  # Si tiene ID pero no es 8 ni 11 caracteres
            pdf.cell(0, 4, f"CE: {cliente_id}", 0, 1)
        else:
            # Si no hay ID, no mostrar nada
            pass

        cliente_nombre = self.data.get('cliente_nombre', 'N/A')
        if len(cliente_nombre) > 35:
            pdf.multi_cell(0, 4, f"CLIENTE: {cliente_nombre}", 0)
        else:
            pdf.cell(0, 4, f"CLIENTE: {cliente_nombre}", 0, 1)

        # Dirección del cliente - solo mostrar si hay datos válidos
        cliente_dir = self.data.get('cliente_direccion', '').strip()
        cliente_dis = self.data.get('cliente_distrito', '').strip()
        cliente_dep = self.data.get('cliente_departamento', '').strip()

        # Filtrar valores no válidos
        valores_invalidos = ['', 'N/A', 'n/a', '-', '--', '---']
        partes_validas = [parte for parte in [cliente_dir, cliente_dis, cliente_dep] 
                        if parte and parte not in valores_invalidos]

        if partes_validas:
            direccion_completa = " - ".join(partes_validas)
            texto_direccion = f"DIRECCIÓN: {direccion_completa}"
            
            if len(texto_direccion) > 35:
                pdf.multi_cell(0, 4, texto_direccion, 0)
            else:
                pdf.cell(0, 4, texto_direccion, 0, 1)
        pdf.ln(2)

        # Línea separadora
        pdf.cell(0, 1, "", "T", 1)
        pdf.set_font("Arial", '', 6)
        pdf.cell(0, 4, f"FORMA DE PAGO: {self.data.get('forma_pago')}", 0, 1)
        
        # Encabezados de la tabla - MEJOR AJUSTE
        pdf.set_font("Arial", 'B', 5)

        # Definir anchuras de columnas (las mismas para encabezado y contenido)
        anchuras = [16, 8, 6, 20, 10, 14]  # COD, CANT, UNID, DESC, V.UNIT, V.VENTA
        total_anchura = sum(anchuras)  # Debe ser 80mm

        # Encabezados de la tabla - CON LAS MISMAS ANCHURAS
        pdf.set_font("Arial", 'B', 5)
        encabezados = ["COD", "CANT.", "UNID.", "DESCRIPCION", "V.UNIT", "V.VENTA"]

        for i, encabezado in enumerate(encabezados):
            pdf.cell(anchuras[i], 5, encabezado, 1, 0, 'C')
        pdf.ln(5)  # Salto de línea después del encabezado

        # Contenido de la tabla - MISMAS ANCHURAS
        pdf.set_font("Arial", '', 6)

        for item in self.data.get('items', []):
            # Preparar datos
            codigo = str(item.get('id', 'N/A'))[:20]
            cantidad = str(item.get('cantidad', '0'))[:6]
            unidad = str(item.get('unidad', 'UND'))[:4]
            descripcion = str(item.get('descripcion', 'N/A'))
            precio_unitario = str(item.get('precio_unitario', '0.00'))[:5]
            total = str(item.get('total', '0.00'))
            
            # Guardar posición inicial
            x_start = pdf.get_x()
            y_start = pdf.get_y()
            
            # Dibujar celdas fijas (COD, CANT, UNID)
            pdf.cell(anchuras[0], 4, codigo, 1, 0, 'C')
            pdf.cell(anchuras[1], 4, cantidad, 1, 0, 'C')
            pdf.cell(anchuras[2], 4, unidad, 1, 0, 'C')
            
            # Celda de descripción con multi_cell
            x_desc = pdf.get_x()
            y_desc = pdf.get_y()
            
            # Usar multi_cell para la descripción (misma anchura)
            pdf.multi_cell(anchuras[3], 4, descripcion, 1, 'c')  # 'L' para alineación izquierda
            
            # Calcular la altura que ocupó la descripción
            desc_height = pdf.get_y() - y_desc
            
            # Posicionar para las celdas restantes
            pdf.set_xy(x_desc + anchuras[3], y_desc)
            
            # Dibujar celdas de precio y total (misma altura que la descripción)
            pdf.cell(anchuras[4], desc_height, precio_unitario, 1, 0, 'c')  # 'R' para números
            pdf.cell(anchuras[5], desc_height, total, 1, 1, 'c')  # 'R' para números
            
            # Ajustar la posición Y para la siguiente fila
            pdf.set_xy(x_start, pdf.get_y())

        pdf.ln(2)
        
        
        # Totales - FUENTE NORMAL
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(50, 5, "TOTAL VENTA:", 0, 0)
        pdf.cell(25, 5, self.format_currency(self.data.get('total_venta', '0.00')), 0, 1, 'R')
        
        pdf.cell(50, 5, "IGV:", 0, 0)
        pdf.cell(25, 5, self.format_currency(self.data.get('total_igv', '0.00')), 0, 1, 'R')
        
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(50, 6, "TOTAL A PAGAR:", 0, 0)
        pdf.cell(25, 6, self.format_currency(self.data.get('total_pagar', '0.00')), 0, 1, 'R')
        pdf.set_font("Arial", '', 6)
        pdf.cell(0, 4, self.data.get('monto_letras'), 0, 1)


        pdf.ln(3)
        pdf.set_font("Arial", '', 6)
        # Unir fecha y hora en un solo formato
        fecha = self.data.get('fecha_emision', 'N/A')
        hora = self.data.get('hora_emision', 'N/A')

        if fecha != 'N/A' and hora != 'N/A':
            # Formatear como "24-08-2025 19:11:20"
            fecha_hora = f"{fecha} {hora}"
            pdf.cell(0, 4, f"Fecha: {fecha_hora}", 0, 1, 'C')
        else:
            # Si falta alguno, mostrar por separado
            pdf.cell(0, 4, f"Fecha: {fecha}", 0, 1, 'C')
            if hora != 'N/A':
                pdf.cell(0, 4, f"Hora: {hora}", 0, 1, 'C')

        pdf.set_font("Arial", 'I', 6)
        pdf.cell(0, 4, "¡Gracias por su compra!", 0, 1, 'C')
        
        # Guardar PDF
        pdf.output(self.output_path)
        print(f"PDF generado: {self.output_path} (Alto calculado: {page_height}mm)")
        #print(f"PDF generado: {self.output_path} (Alto: {page_height}mm)")

def main():
    # Configurar rutas
    input_dir = "input"
    output_dir = "output"
    
    # Crear directorios si no existen
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    # Procesar todos los archivos XML en el directorio de entrada
    xml_files = [f for f in os.listdir(input_dir) if f.endswith('.xml')]
    
    if not xml_files:
        print("No se encontraron archivos XML en la carpeta 'input'")
        print("Por favor, coloca los archivos XML en la carpeta 'input'")
        return
    
    for filename in xml_files:
        xml_path = os.path.join(input_dir, filename)
        pdf_filename = filename.replace('.xml', '.pdf')
        output_path = os.path.join(output_dir, pdf_filename)
        
        print(f"\nProcesando: {filename}")
        
        # Crear instancia y procesar
        factura = FacturaXMLtoPDF(xml_path, output_path)
        if factura.parse_xml():
            factura.generate_pdf()
            print(f"✓ Datos extraídos correctamente")
        else:
            print(f"✗ Error al procesar {filename}")

if __name__ == "__main__":
    main()