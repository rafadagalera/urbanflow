"""Pipeline de dados do UrbanCare (bronze → silver → gold).

Os módulos não dependem do Airflow: leem DATABASE_URL e URBANCARE_DATA_DIR do
ambiente, para poderem rodar também via `python -m urbancare_pipeline`.
"""
