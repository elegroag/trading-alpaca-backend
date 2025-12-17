from flask import Flask, jsonify, request

from utils.auth_utils import require_auth
from services.news_scraper_service import news_scraper_service, NewsScraperServiceException


def register_news_routes(app: Flask) -> None:
    @app.route('/api/news/<symbol>', methods=['GET'])
    @require_auth
    def get_news(symbol: str):
        try:
            limit_raw = request.args.get('limit', '10')
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                return jsonify({'success': False, 'error': 'Parámetro limit debe ser un número'}), 400

            items = news_scraper_service.get_news(symbol, limit=limit)
            return jsonify({'success': True, 'data': items})
        except NewsScraperServiceException as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception:
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500
