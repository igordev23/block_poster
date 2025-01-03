from flask import Flask, render_template, request, send_file, redirect, url_for, session
from PIL import Image, ImageDraw, ImageOps
from fpdf import FPDF
import os
import shutil

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

# Ensure upload and output folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.add_url_rule('/uploads/<filename>', 'uploaded_file', build_only=True)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return "No image uploaded!"
    
    file = request.files['image']
    if file.filename == '':
        return "No selected file!"

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)
    session['image_path'] = file.filename  # Salve apenas o nome do arquivo

    image = Image.open(filepath)
    session['image_size'] = image.size
    return redirect(url_for('preview'))



@app.route('/preview', methods=['GET', 'POST'])
def preview():
    if 'image_path' not in session:
        return redirect(url_for('index'))

    image_path = session['image_path']
    image_size = session['image_size']

    rows = int(request.form.get('rows', 1))
    cols = int(request.form.get('cols', 1))

    # Calcula dimensões do tile
    tile_width = image_size[0] // cols
    tile_height = image_size[1] // rows

    return render_template(
        'preview.html',
        image_path=image_path,
        image_size=image_size,
        rows=rows,
        cols=cols,
        tile_width=tile_width,
        tile_height=tile_height
    )


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))


@app.route('/process', methods=['POST'])
def process_image():
    if 'image_path' not in session:
        return redirect(url_for('index'))

    image_path = os.path.join(app.config['UPLOAD_FOLDER'], session['image_path'])

    if not os.path.exists(image_path):
        return "Imagem não encontrada!", 404

    cols = int(request.form['cols'])
    orientation = request.form['orientation']
    include_borders = 'borders' in request.form

    # Abre a imagem usando o caminho completo
    image = Image.open(image_path)

    # Chamar a lógica correta com base na orientação
    if orientation == 'landscape':
        return process_landscape(image, cols, include_borders)
    else:  # 'portrait'
        return process_portrait(image, cols, include_borders)


def process_landscape(image, cols, include_borders):
    """Lógica específica para orientação landscape."""
    img_width, img_height = image.size

    # Dimensões da folha A4 em pixels (landscape)
    page_width, page_height = 3508, 2480

    # Calcula o número de linhas
    aspect_ratio = img_height / img_width
    rows = int(cols * (1 / aspect_ratio))

    tile_width = img_width // cols
    tile_height = img_height // rows

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    temp_files = []

    for row in range(rows):
        for col in range(cols):
            left = col * tile_width
            top = row * tile_height
            right = min(left + tile_width, img_width)
            bottom = min(top + tile_height, img_height)

            tile = image.crop((left, top, right, bottom))

            # Se incluir bordas, adiciona a borda mínima sem perder proporcionalidade
            if include_borders:
                # Define uma borda mínima, pode ser ajustada conforme necessário
                border_size = 10
                tile = ImageOps.expand(tile, border=border_size, fill=(255, 255, 255))

            # Ajustar tamanho da imagem para preencher a folha A4
            tile = tile.resize((page_width, page_height), Image.Resampling.LANCZOS)

            temp_path = os.path.join(OUTPUT_FOLDER, f"tile_{row+1}_{col+1}.jpg")
            tile.save(temp_path, format="JPEG")
            temp_files.append(temp_path)

            pdf.add_page()
            pdf.image(temp_path, x=0, y=0, w=297, h=210)  # Preenche toda a página A4

    pdf_output_path = os.path.join(OUTPUT_FOLDER, "output_landscape.pdf")
    pdf.output(pdf_output_path)

    for temp_file in temp_files:
        os.remove(temp_file)

    session['pdf_path'] = pdf_output_path
    return redirect(url_for('download'))

def process_portrait(image, cols, include_borders):
    """Lógica específica para orientação portrait."""
    img_width, img_height = image.size
    aspect_ratio = img_height / img_width  # Calcula a proporção da imagem original

    # Dimensões da folha A4 em pixels (portrait)
    page_width, page_height = 2480, 3508

    rows = int(cols * aspect_ratio)  # Calcula o número de linhas automaticamente
    tile_width = img_width // cols
    tile_height = img_height // rows

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    temp_files = []

    for row in range(rows):
        for col in range(cols):
            left = col * tile_width
            top = row * tile_height
            right = min(left + tile_width, img_width)
            bottom = min(top + tile_height, img_height)

            tile = image.crop((left, top, right, bottom))

            # Ajustar tamanho da imagem para preencher a folha A4
            if include_borders:
                border_size = 20
                tile = tile.resize((page_width - 2 * border_size, page_height - 2 * border_size), Image.Resampling.LANCZOS)

                # Adicionar fundo branco para bordas
                background = Image.new("RGB", (page_width, page_height), (255, 255, 255))
                paste_x = border_size
                paste_y = border_size
                background.paste(tile, (paste_x, paste_y))
                tile = background
            else:
                tile = tile.resize((page_width, page_height), Image.Resampling.LANCZOS)

            temp_path = os.path.join(OUTPUT_FOLDER, f"tile_{row+1}_{col+1}.jpg")
            tile.save(temp_path, format="JPEG")
            temp_files.append(temp_path)

            pdf.add_page()
            pdf.image(temp_path, x=0, y=0, w=210, h=297)  # Preenche toda a página A4

    pdf_output_path = os.path.join(OUTPUT_FOLDER, "output_portrait.pdf")
    pdf.output(pdf_output_path)

    for temp_file in temp_files:
        os.remove(temp_file)

    session['pdf_path'] = pdf_output_path
    return redirect(url_for('download'))


@app.route('/download')
def download():
    if 'pdf_path' not in session:
        return redirect(url_for('index'))

    pdf_path = session['pdf_path']
    return render_template('download.html', pdf_path=pdf_path)

@app.route('/download_pdf')
def download_pdf():
    if 'pdf_path' not in session:
        return redirect(url_for('index'))

    pdf_path = session['pdf_path']
    return send_file(pdf_path, as_attachment=True)

@app.route('/reset')
def reset():
    session.clear()

    # Fecha todos os arquivos abertos e limpa recursos
    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
        if os.path.exists(folder):
            for root, dirs, files in os.walk(folder):
                for file in files:
                    try:
                        os.remove(os.path.join(root, file))
                    except PermissionError:
                        continue  # Ignore arquivos em uso
            try:
                shutil.rmtree(folder)
            except PermissionError:
                continue  # Ignore se a pasta ainda estiver em uso

    # Recria as pastas
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(debug=True)
