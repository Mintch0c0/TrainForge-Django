# TrainForge

TrainForge is a Django-based personal trainer management system developed as a university web application project. It brings client management, training plans, appointments, progress tracking, subscriptions, and AI-assisted coaching tools into one dashboard.

## Main Features

- **Authentication** – Email/password signup and login, plus Google and GitHub OAuth through Django Allauth.
- **Dashboard** – Overview of clients, active plans, upcoming sessions, session frequency, recent activity, and AI-generated insights.
- **Client Management** – Add, view, edit, and delete clients, save preferred appointment times, and generate AI-assisted notes and plan suggestions.
- **Training Plans** – Create and manage multi-day workout plans with exercises, sets, reps, rest time, descriptions, and trainer notes.
- **Appointments** – Schedule and manage appointments using a calendar-style interface, with AI-assisted scheduling suggestions.
- **Progress Tracking** – Record weight and repetition progress, review recent logs, and generate coaching insights from progress trends.
- **Trainer Subscriptions** – Create, edit, archive, and filter trainer subscriptions by status and plan tier.

## Technologies Used

- Python
- Django
- SQLite
- HTML
- CSS
- JavaScript
- Django Allauth
- Google OAuth
- GitHub OAuth
- OpenAI API

## Project Structure

```text
TrainForge/
├── core/               # Models, views, URLs and application logic
├── static/             # CSS and other static assets
├── templates/          # Django HTML templates
├── trainforge/         # Django project settings and configuration
├── .env.example        # Example environment variables
├── .gitignore
├── manage.py
├── requirements.txt
└── README.md
```

## Local Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd TrainForge
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

On macOS/Linux:

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to a new file named `.env` and replace the placeholder values:

```env
SECRET_KEY=your_django_secret_key
OPENAI_API_KEY=your_openai_api_key
DEBUG=True
```

The `.env` file is intentionally excluded from Git and should never be committed.

### 5. Set up the database

```bash
python manage.py migrate
```

Create your own administrator account:

```bash
python manage.py createsuperuser
```

### 6. Run the application

```bash
python manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/
```

The Django admin panel is available locally at:

```text
http://127.0.0.1:8000/admin/
```

## Google and GitHub Login

Third-party authentication is implemented with Django Allauth. To use Google or GitHub login locally, create OAuth applications with the relevant providers and configure their credentials through Django's admin **Social Applications** section.

Example local callback URLs:

```text
http://127.0.0.1:8000/accounts/google/login/callback/
http://127.0.0.1:8000/accounts/github/login/callback/
```

OAuth client IDs and secrets should not be committed to this repository.

## AI Features

TrainForge uses the OpenAI API to support features such as client note suggestions, training plan suggestions, scheduling assistance, dashboard insights, and coaching insights. A personal API key must be provided through the local `.env` file for these features to work.

## Security Notes

This public repository intentionally excludes local/private development data and credentials, including:

- `.env`
- `db.sqlite3`
- API keys and OAuth secrets
- Local user/admin credentials
- Python cache files

## Author

**Febriani Patricia**  
Bachelor of Information Technology  
The University of Queensland
2026
