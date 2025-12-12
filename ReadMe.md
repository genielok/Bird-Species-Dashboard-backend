# Backend — Acoustic Processing Tool

This backend provides **bird sound analysis**, **audio preprocessing**, and **AWS Step Functions integration** for the Acoustic Processing Tool.  
It uses **BirdNET**, **AWS ECS**, **Step Functions**, and **S3** to run large‑scale bird species detection workflows.

---

## 🐍 Installation

### 1. Python Environment

Ensure Python version **≤ 3.11**:

```bash
pip install birdnet
pip install -r requirements.txt
uvicorn app.main:app --reload
```



