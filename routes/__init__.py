from flask import Blueprint
from routes.users import users_bp
from routes.batches import batches_bp
from routes.transactions import transactions_bp
from routes.blockchain_api import blockchain_bp

def init_routes(app):
    app.register_blueprint(users_bp, url_prefix='/api')
    app.register_blueprint(batches_bp, url_prefix='/api')
    app.register_blueprint(transactions_bp, url_prefix='/api')
    app.register_blueprint(blockchain_bp, url_prefix='/api')

    # Template pages (server-rendered)
    @app.route('/')
    def login():
        from flask import render_template
        return render_template('login.html')

    @app.route('/template/dashboard')
    def dashboard_page():
        from flask import render_template
        return render_template('dashboard.html')

    @app.route('/template/track')
    def track_page():
        from flask import render_template
        return render_template('track_batch.html')

    @app.route('/template/new-batch')
    def new_batch_page():
        from flask import render_template
        return render_template('new_batch.html')
        
    @app.route('/template/users')
    def users_page():
        from flask import render_template
        return render_template('users.html')

    @app.route('/template/blockchain')
    def blockchain_page():
        from flask import render_template
        return render_template('blockchain.html')

    @app.route('/template/settings')
    def settings_page():
        from flask import render_template
        return render_template('settings.html')

    @app.route('/template/verify')
    def verify_page():
        from flask import render_template
        return render_template('verify_qr.html')