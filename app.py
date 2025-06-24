from flask import Flask, request, Response, jsonify, session
from flask_cors import CORS
from kaggle.api.kaggle_api_extended import KaggleApi
import requests
import os
import uuid
from urllib.parse import urljoin, urlparse
import json
from datetime import datetime

app = Flask(__name__)
CORS(app, supports_credentials=True, resources={
    r"/*": {"origins": "http://127.0.0.1:5500"}
})
# Store session data for each instance
instance_sessions = {}

# Home route
@app.route('/')
def home():
    return '✅ Flask backend is running on Render with Multi-Instance Browser support.'

# Create a new browser instance
@app.route('/create-instance', methods=['POST'])
def create_instance():
    try:
        data = request.get_json()
        instance_id = str(uuid.uuid4())
        
        # Initialize session storage for this instance
        instance_sessions[instance_id] = {
            'cookies': {},
            'headers': {},
            'created_at': datetime.now().isoformat(),
            'name': data.get('name', 'Unnamed Instance'),
            'base_url': data.get('url', '')
        }
        
        return jsonify({
            'success': True,
            'instance_id': instance_id,
            'message': 'Instance created successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Delete a browser instance
@app.route('/delete-instance/<instance_id>', methods=['DELETE'])
def delete_instance(instance_id):
    try:
        if instance_id in instance_sessions:
            del instance_sessions[instance_id]
            return jsonify({
                'success': True,
                'message': 'Instance deleted successfully'
            })
        else:
            return jsonify({'error': 'Instance not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Get all instances
@app.route('/instances', methods=['GET'])
def get_instances():
    try:
        instances = []
        for instance_id, data in instance_sessions.items():
            instances.append({
                'id': instance_id,
                'name': data['name'],
                'base_url': data['base_url'],
                'created_at': data['created_at']
            })
        return jsonify({'instances': instances})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Proxy requests for specific instance
@app.route('/proxy/<instance_id>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy_request(instance_id):
    try:
        if instance_id not in instance_sessions:
            return jsonify({'error': 'Instance not found'}), 404
        
        # Get the target URL from query parameter
        target_url = request.args.get('url')
        if not target_url:
            return jsonify({'error': 'URL parameter required'}), 400
        
        # Prepare the request
        method = request.method
        headers = dict(request.headers)
        
        # Remove headers that shouldn't be forwarded
        headers_to_remove = ['Host', 'Origin', 'Referer']
        for header in headers_to_remove:
            headers.pop(header, None)
        
        # Add stored headers for this instance
        instance_data = instance_sessions[instance_id]
        if 'headers' in instance_data:
            headers.update(instance_data['headers'])
        
        # Prepare cookies for this instance
        cookies = instance_data.get('cookies', {})
        
        # Make the request
        if method == 'GET':
            response = requests.get(
                target_url, 
                headers=headers, 
                cookies=cookies,
                allow_redirects=True,
                timeout=30
            )
        elif method == 'POST':
            response = requests.post(
                target_url,
                headers=headers,
                cookies=cookies,
                data=request.get_data(),
                allow_redirects=True,
                timeout=30
            )
        else:
            response = requests.request(
                method,
                target_url,
                headers=headers,
                cookies=cookies,
                data=request.get_data(),
                allow_redirects=True,
                timeout=30
            )
        
        # Store cookies from response for this instance
        if response.cookies:
            for cookie in response.cookies:
                instance_sessions[instance_id]['cookies'][cookie.name] = cookie.value
        
        # Create response
        excluded_headers = [
    'content-encoding',
    'content-length',
    'transfer-encoding',
    'connection',
    'x-frame-options',
    'content-security-policy'  
]
        response_headers = [(name, value) for (name, value) in response.headers.items()
                          if name.lower() not in excluded_headers]
        
        # Modify content if it's HTML to fix relative URLs
        content = response.content
        if 'text/html' in response.headers.get('content-type', ''):
            try:
                content_str = content.decode('utf-8')
                # Replace relative URLs with proxy URLs
                base_url = f"{request.scheme}://{request.host}/proxy/{instance_id}"
                parsed_target = urlparse(target_url)
                target_base = f"{parsed_target.scheme}://{parsed_target.netloc}"
                
                # Replace common relative URL patterns
                content_str = content_str.replace('href="/', f'href="{base_url}?url={target_base}/')
                content_str = content_str.replace('src="/', f'src="{base_url}?url={target_base}/')
                content_str = content_str.replace("href='/", f"href='{base_url}?url={target_base}/")
                content_str = content_str.replace("src='/", f"src='{base_url}?url={target_base}/")
                
                content = content_str.encode('utf-8')
            except:
                pass  # If decoding fails, return original content
        
        return Response(
            content,
            status=response.status_code,
            headers=response_headers
        )
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Request failed: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Dynamic Kaggle dataset file listing (keeping your original functionality)
@app.route('/list-files/<owner>/<dataset>')
def list_kaggle_files(owner, dataset):
    try:
        # Authenticate using env vars
        api = KaggleApi()
        api.authenticate()
        # Build full dataset identifier
        dataset_path = f"{owner}/{dataset}"
        # Fetch file list
        files = api.dataset_list_files(dataset_path).files
        file_names = [f.name for f in files]
        return jsonify({
            "dataset": dataset_path,
            "file_count": len(file_names),
            "files": file_names
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
