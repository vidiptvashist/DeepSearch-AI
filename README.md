# **DeepSearch AI — AI-Powered Document Intelligence**

DeepSearch AI is a full-stack platform that lets users upload documents, search them using natural language, and get accurate insights powered by **Google Gemini’s File Search API**.
The system includes **authentication, secure file storage, multi-store organization, and a clean modern UI**, making it ideal for research, knowledge management, and internal document search.

![ezgif com-animated-gif-maker](https://github.com/user-attachments/assets/9c75a11d-8c85-46d3-a403-3ab0e63bae92)


## 🚀 **Features**

### 🔐 **User Authentication (Supabase)**

* Email + password sign-up & login
* Secure session management
* Protected routes & user-scoped data isolation
* Logout and user profile display (shows username extracted from email)

### 📄 **Document File Search (Gemini API)**

DeepSearch AI uses:

* **Gemini File Storage** for uploading PDFs/TXT/DOCX
* **Gemini File Search Tool-Calling** to query files with structured semantic search
* **Citations and context-aware answers** returned from Gemini

More info: [https://ai.google.dev/gemini-api/docs/file-search](https://ai.google.dev/gemini-api/docs/file-search)

### 🗂️ **Organized Document Stores**

* Each user can create multiple “stores”
* Stores help organize documents by project/topic
* Upload/delete documents inside each store
* Query a store and get AI answers with citations

### ⚡ **Modern, Clean UI**

* Fully responsive landing page
* Login & signup pages with modern card UI
* Dashboard inspired by SaaS document-search apps
* Dark mode toggle
* Smooth interaction flow:
  **Landing → Auth → Dashboard → Store → Upload → Ask AI**

### 🧪 **AI-Powered Search**

Ask questions in natural language:

* “Summarize the main findings of this research paper.”
* “Compare methods used across all stored documents.”
* “What does section 4.2 state about methodology?”

Gemini File Search returns **precise, contextual answers**.

---

# 📁 **Repository Structure**

```
README.md
requirements.txt
app/
    main.py                # FastAPI entrypoint
    deps.py                # Superbase
    gemini_client.py       # Gemini file search + model wrapper

static/
    index.html             # UI
```

---

# 🔧 **Setup Instructions**

## 1️⃣ **Clone the repo**

```bash
git clone https://github.com/<your-username>/DeepSearch-AI.git
cd DeepSearch-AI
```

---

## 2️⃣ **Backend Setup (FastAPI)**

### Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install dependencies:

```bash
pip install -r requirements.txt
```

### Environment variables:

Create a `.env` file:

```
# Gemini
GEMINI_API_KEY=

# Supabase Auth
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=
```

---

## 3️⃣ **Run Backend**

```bash
python app/main.py
```

Backend will start at:

```
http://localhost:8000
```

---

# 🎨 **Frontend 


Frontend available at:

```
http://localhost:8000
```

---

# 🔥 **User Flow**

### 1. **Landing Page**

Large hero section, marketing text, CTA button → “Get Started Free”.

### 2. **Sign Up / Login**

Clean authentication card with:

* Email input
* Password input
* Sign-in / Sign-up toggle

### 3. **Dashboard**

After login:

* Sidebar with list of stores
* Add new store
* User name displayed (first part of email)

### 4. **Store View**

Inside each store:

* Upload PDF/DOC/TXT
* View list of uploaded documents
* Delete docs
* Query input (Ask AI)

### 5. **AI-Powered Search**

Backend sends query → Gemini File Search → returns answer with citations.


---

# 📬 **Support**

Open an issue for bugs, feature requests, or integration questions.

