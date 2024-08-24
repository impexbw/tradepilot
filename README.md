# TradePilot

## Overview
TradePilot is a comprehensive trading journal and analytics platform designed to help traders track, manage, and analyze their trades effectively. Built using Python, this project integrates various tools and features to provide detailed insights into trading performance, making it an essential tool for any serious trader.

## Setup Instructions

### 1. Clone the Repository
To get started, clone the repository to your local machine:

```bash
git clone https://github.com/impexbw/tradepilot.git
cd tradepilot
```

### 2. Create a Virtual Environment
It's highly recommended to use a virtual environment to manage your Python dependencies. If you don't already have `venv` installed, you can install it by running:

```bash
pip install virtualenv
```

Next, create a virtual environment in the project directory:

```bash
python -m venv venv
```

Activate the virtual environment:

- On **Windows**:
  ```bash
  venv\Scripts\activate
  ```
- On **macOS/Linux**:
  ```bash
  source venv/bin/activate
  ```

### 3. Install Dependencies
With the virtual environment activated, install the project dependencies listed in the `requirements.txt` file:

```bash
pip install -r requirements.txt
```

### 4. Configure the Database
Edit the `__init__.py` file to configure the database connection string with your own database credentials:

Open the `__init__.py` file located in the project directory, and adjust the following line to match your database configuration:

```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://your-username:your-password@localhost/your-database-name'
```

Replace `your-username`, `your-password`, and `your-database-name` with your MySQL credentials and the name of your database.

### 5. Set Up Flask Environment
Before running database migrations, set the `FLASK_APP` environment variable to point to your application file:

- **For Windows PowerShell:**

  ```bash
  $env:FLASK_APP = "run.py:tradepilot"
  ```

- **For Windows CMD:**

  ```bash
  set FLASK_APP=run.py:tradepilot
  ```

- **For macOS/Linux:**

  ```bash
  export FLASK_APP=run.py:tradepilot
  ```

### 6. Create and Apply Database Migrations
Once the environment is set, you can create and apply database migrations:

```bash
flask --app tradepilot db init
flask --app tradepilot db migrate -m "Initial migration."
flask --app tradepilot db upgrade
```

### 7. Running the Project
After installing the dependencies and setting up the database, you can run the project by executing:

```bash
python run.py
```

Replace `run.py` with the actual entry point of your project if it's different.

### 8. Deactivating the Virtual Environment
When you're done working on the project, you can deactivate the virtual environment by running:

```bash
deactivate
```

## Contributing
If you'd like to contribute to the project, please fork the repository and use a feature branch. Pull requests are welcome.

## Author
This project was created and is maintained by Ludovic Micinthe.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
