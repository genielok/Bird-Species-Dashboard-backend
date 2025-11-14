FROM python:3.10-slim

# 安装依赖
RUN apt-get update && apt-get install -y git

# 安装 Perch Hoplite
RUN pip install perch-hoplite
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
    
RUN pip install "numpy<2.1.0"

# 设置工作目录
WORKDIR /app

# 拷贝 demo 脚本
COPY demo.py /app/demo.py

# 运行脚本
CMD ["python", "demo.py"]
