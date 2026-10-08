# CPU image: Python 3.11 + .NET 8 + FamiStudio 4.5.2 + ffmpeg
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    DOTNET_ROOT=/usr/share/dotnet \
    PATH="/usr/share/dotnet:/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip ffmpeg libsndfile1 \
      software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      python3.11 python3.11-venv python3.11-dev \
    && rm -rf /var/lib/apt/lists/*

# .NET 8 runtime for FamiStudio
RUN curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh \
    && bash /tmp/dotnet-install.sh --channel 8.0 --runtime dotnet --install-dir /usr/share/dotnet \
    && ln -sf /usr/share/dotnet/dotnet /usr/local/bin/dotnet

WORKDIR /app
COPY . /app

RUN chmod +x /app/setup.sh \
    && /app/setup.sh \
    && mkdir -p /app/artifacts

EXPOSE 43187
# Default: web UI. Override with e.g. `audio2fami song.mp3 -f mp3 -o /out/out.mp3`
CMD ["audio2fami", "ui", "--host", "0.0.0.0", "--port", "43187"]
