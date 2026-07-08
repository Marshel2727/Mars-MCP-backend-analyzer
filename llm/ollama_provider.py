import json

import requests

from config.settings import (
  OLLAMA_BASE_URL,
  OLLAMA_KEEP_ALIVE,
  OLLAMA_MAIN_GPU,
  OLLAMA_MODEL,
  OLLAMA_NUM_CTX,
  OLLAMA_NUM_GPU,
  OLLAMA_NUM_PREDICT,
  OLLAMA_REPEAT_PENALTY,
  OLLAMA_TEMPERATURE,
  OLLAMA_TIMEOUT,
  OLLAMA_TOP_P,
)
from llm.provider import LLMProvider


class OllamaProvider(LLMProvider):
  def __init__(
    self,
    base_url: str = OLLAMA_BASE_URL,
    model: str = OLLAMA_MODEL,
    timeout: int = OLLAMA_TIMEOUT,
    num_ctx: int = OLLAMA_NUM_CTX,
    num_gpu: int = OLLAMA_NUM_GPU,
    main_gpu: int = OLLAMA_MAIN_GPU,
    temperature: float = OLLAMA_TEMPERATURE,
    top_p: float = OLLAMA_TOP_P,
    num_predict: int = OLLAMA_NUM_PREDICT,
    repeat_penalty: float = OLLAMA_REPEAT_PENALTY,
    keep_alive: str = OLLAMA_KEEP_ALIVE,
  ):
    self.base_url = base_url.rstrip("/")
    self.model = model
    self.timeout = timeout
    self.num_ctx = num_ctx
    self.num_gpu = num_gpu
    self.main_gpu = main_gpu
    self.temperature = temperature
    self.top_p = top_p
    self.num_predict = num_predict
    self.repeat_penalty = repeat_penalty
    self.keep_alive = keep_alive

  def build_options(
    self,
    num_predict: int | None = None,
    temperature: float | None = None,
  ) -> dict:
    return {
      "num_ctx": self.num_ctx,
      "num_gpu": self.num_gpu,
      "main_gpu": self.main_gpu,
      "temperature": self.temperature if temperature is None else temperature,
      "top_p": self.top_p,
      "num_predict": self.num_predict if num_predict is None else num_predict,
      "repeat_penalty": self.repeat_penalty,
    }

  def generate(
    self,
    prompt: str,
    num_predict: int | None = None,
    temperature: float | None = None,
  ) -> str:
    try:
      response = requests.post(
        f"{self.base_url}/api/generate",
        json={
          "model": self.model,
          "prompt": prompt,
          "stream": False,
          "keep_alive": self.keep_alive,
          "options": self.build_options(
            num_predict=num_predict,
            temperature=temperature,
          ),
        },
        timeout=self.timeout,
      )

      response.raise_for_status()
    except requests.exceptions.ConnectionError as error:
      raise ConnectionError(
        f"Ollama tidak bisa dihubungi di {self.base_url}. "
        "Pastikan Ollama sedang berjalan."
      ) from error
    except requests.exceptions.Timeout as error:
      raise TimeoutError(
        f"Ollama melewati batas waktu {self.timeout} detik. "
        "Coba pakai --depth normal, turunkan OLLAMA_NUM_PREDICT, "
        "atau gunakan model yang lebih cepat."
      ) from error
    except requests.exceptions.HTTPError as error:
      raise RuntimeError(
        f"Ollama mengembalikan error {response.status_code}: {response.text}"
      ) from error

    data = response.json()

    return data.get("response", "")

  def generate_stream(
    self,
    prompt: str,
    num_predict: int | None = None,
    temperature: float | None = None,
  ):
    try:
      with requests.post(
        f"{self.base_url}/api/generate",
        json={
          "model": self.model,
          "prompt": prompt,
          "stream": True,
          "keep_alive": self.keep_alive,
          "options": self.build_options(
            num_predict=num_predict,
            temperature=temperature,
          ),
        },
        stream=True,
        timeout=(10, self.timeout),
      ) as response:
        response.raise_for_status()

        for line in response.iter_lines(decode_unicode=True):
          if not line:
            continue

          data = json.loads(line)
          chunk = data.get("response", "")

          if chunk:
            yield chunk

          if data.get("done"):
            break
    except requests.exceptions.ConnectionError as error:
      raise ConnectionError(
        f"Ollama tidak bisa dihubungi di {self.base_url}. "
        "Pastikan Ollama sedang berjalan."
      ) from error
    except requests.exceptions.Timeout as error:
      raise TimeoutError(
        f"Ollama melewati batas waktu {self.timeout} detik. "
        "Coba kurangi --max-files atau pakai model lebih kecil."
      ) from error
    except requests.exceptions.HTTPError as error:
      raise RuntimeError(
        f"Ollama mengembalikan error {response.status_code}: {response.text}"
      ) from error
