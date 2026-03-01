import httpx

def main():
    h = httpx.get("http://localhost:8000/health")
    print("Health:", h.status_code, h.text)
    r = httpx.post("http://localhost:8000/recommend", json={"query": "Need a Python developer who collaborates well"})
    print("Recommend:", r.status_code)
    print(r.text)

if __name__ == "__main__":
    main()
