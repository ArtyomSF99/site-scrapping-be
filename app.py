import os
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, render_template, send_from_directory
import subprocess
from flask_cors import CORS
import sys
from flask_cors import cross_origin
from urllib.parse import quote as url_quote

if sys.version_info < (3, 8):
    required_python_version = ".".join(map(str, (3, 8)))
    current_python_version = ".".join(map(str, sys.version_info[:2]))
    sys.exit(f"[ERROR] Required Python version is [{required_python_version}] or higher, current version is [{current_python_version}]")

try:
    pip_version = subprocess.check_output(["pip", "--version"]).decode().split()[1]
    required_pip_version = "23.2"
    if pip_version < required_pip_version:
        sys.exit(f"[ERROR] Required pip version is [{required_pip_version}] or higher, current version is [{pip_version}]")
except (subprocess.CalledProcessError, FileNotFoundError):
    sys.exit("[ERROR] pip is not available or not working properly")

port = int(os.environ.get("PORT", 8080))

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/generate_site', methods=['POST'])
def generate_site():
    data = request.get_json()
    if data is not None:
        url = data['url']
        slug = data['slug']
        title = data['title']
        template = data.get('template', '0')
        font = data.get('font', 'DMSans')
        try:
            subprocess.check_output(['python3', 'generate_site.py', url, slug, title, template, font], stderr=subprocess.STDOUT, text=True)
            return send_from_directory(app.static_folder, f'{slug}/index.html')
        except subprocess.CalledProcessError as e:
            return jsonify({"error": e.output, "request": request}), 500
    else:
        return jsonify({"error": "Missing parameters"}), 400
    
@app.route('/edit_generated_site', methods=['PUT'])
@cross_origin(methods=['PUT'], headers=['Content-Type'])
def edit_generated_site():
    data = request.get_json()
    if data is not None:
        slug = data['slug']
        template = data.get('template', '1')
        font = data.get('font', '0')
        try:
            subprocess.check_output(['python3', 'edit_generated_site.py', slug, template, font], stderr=subprocess.STDOUT, text=True)
            return send_from_directory(app.static_folder, f'{slug}/index.html')
        except subprocess.CalledProcessError as e:
            return jsonify({"error": e.output, "request": request}), 500
    else:
        return jsonify({"error": "Missing parameters"}), 400

@app.route('/edit_template', methods=['PUT'])
@cross_origin(methods=['PUT'], headers=['Content-Type'])
def edit_template():
    data = request.get_json()
    if data is not None:
        slug = data['slug']
        html = data.get('html')
        try:
            soup = BeautifulSoup(html, 'html.parser')
            file_path = os.path.join(app.static_folder, slug, 'index.html')

            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(soup.prettify())

            return send_from_directory(app.static_folder, f'{slug}/index.html')
        except Exception as e:
            return jsonify({"error": str(e), "request": request}), 500
    else:
        return jsonify({"error": "Missing parameters"}, 400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)


