import os
import json
import threading
import uuid
import sys
import subprocess
from queue import Queue
from flask import Flask, request, jsonify, send_from_directory, send_file, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__, static_folder='static')

CORS(app)

# In-memory job storage
jobs = {}

class Job:
    def __init__(self, pdf_path: str, pages: int):
        self.id = str(uuid.uuid4())
        self.pdf_path = pdf_path
        self.pages = pages
        self.status = 'pending'
        self.log_queue = Queue()
        self.result = {}

    def run(self):
        # Mark as running and log start
        self.status = 'running'
        filename = os.path.basename(self.pdf_path)
        self.log_queue.put(f"Processing PDF: {filename}")

        # Prepare environment to preserve UTF-8
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        # Build command using same Python interpreter
        cmd = [
            sys.executable,
            os.path.join(os.getcwd(), 'pipeline.py'),
            '--input-pdf', self.pdf_path,
            '--pages', str(self.pages)
        ]

                # Launch subprocess
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=os.getcwd(),
            env=env
        )

        # Stream logs from subprocess from subprocess
        for line in proc.stdout:
            self.log_queue.put(line.strip())
        proc.wait()

        # Prepare result filenames (no directories)
        base_name = os.path.splitext(os.path.basename(self.pdf_path))[0]
        self.result = {
            'narrative': f"{base_name}_narrative.txt",
            'sankey':    f"{base_name}_sankey.html"
        }

        # Final log and status
        self.log_queue.put('Pipeline complete!')
        self.status = 'completed' if proc.returncode == 0 else 'failed'

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/upload_pdf', methods=['POST'])
def upload_pdf():
    # Validate upload
    if 'file' not in request.files:
        return jsonify({'error': 'File part missing'}), 400
    file = request.files['file']
    pages = int(request.form.get('pages', 3))
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Save PDF to results directory
    filename = secure_filename(file.filename)
    results_dir = os.path.join(os.getcwd(), 'results')
    os.makedirs(results_dir, exist_ok=True)
    pdf_path = os.path.join(results_dir, filename)
    file.save(pdf_path)

    # Start job
    job = Job(pdf_path=pdf_path, pages=pages)
    jobs[job.id] = job
    threading.Thread(target=job.run, daemon=True).start()
    return jsonify({'job_id': job.id})

@app.route('/api/status/<job_id>')
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'status': 'unknown'}), 404
    return jsonify({'status': job.status})

@app.route('/api/logs/<job_id>')
def logs(job_id):
    job = jobs.get(job_id)
    if not job:
        return abort(404)
    def stream():
        while True:
            line = job.log_queue.get()
            yield f"data: {line}\n\n"
            if line.strip().endswith('Pipeline complete!'):
                break
    return app.response_class(stream(), mimetype='text/event-stream')

@app.route('/api/results/<job_id>')
def results(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    if job.status != 'completed':
        return jsonify({'status': job.status}), 400
    return jsonify(job.result)

@app.route('/api/download/<path:filename>')
def download(filename):
    results_dir = os.path.join(os.getcwd(), 'results')
    full_path = os.path.join(results_dir, filename)
    if not os.path.isfile(full_path):
        return abort(404)
    return send_file(full_path, as_attachment=False)

if __name__ == '__main__':
    os.makedirs('results', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
