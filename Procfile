web: gunicorn --workers 2 --worker-class sync --bind 0.0.0.0:$PORT app:app
release: python -c "from database import init_db; init_db()"
