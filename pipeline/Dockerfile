FROM apache/airflow:2.10.5-python3.12

USER airflow
ARG AIRFLOW_VERSION=2.10.5
ARG PYTHON_VERSION=3.12
# Pacotes já presentes nas constraints do Airflow ficam travados nelas;
# scipy, pyproj e geopandas não estão lá e são fixados aqui.
RUN pip install --no-cache-dir \
      --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt" \
      pyarrow shapely requests pytest \
      scipy==1.14.1 pyproj==3.7.0 geopandas==1.0.1
