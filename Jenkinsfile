pipeline {
    agent any

    environment {
        PYTHON_ENV = "venv"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                bat """
                python -m venv %PYTHON_ENV%
                call %PYTHON_ENV%\\Scripts\\activate && pip install -r requirements.txt
                """
            }
        }

        stage('Static Analysis & Linting') {
            steps {
                bat """
                call %PYTHON_ENV%\\Scripts\\activate && pip install flake8 && flake8 . --exclude=%PYTHON_ENV% --count --select=E9,F63,F7,F82 --show-source --statistics
                """
            }
        }

        stage('Run Tests') {
            steps {
                bat """
                call %PYTHON_ENV%\\Scripts\\activate && pip install pytest && pytest
                """
            }
        }

        stage('Deploy (Local)') {
            steps {
                bat """
                @echo off
                :: Intenta cerrar uvicorn si ya está corriendo, si no, ignora el error
                taskkill /F /IM uvicorn.exe /T 2>nul || echo Uvicorn no estaba en ejecucion.
                
                :: Lanza uvicorn en segundo plano
                call %PYTHON_ENV%\\Scripts\\activate && start /B uvicorn main:app --host 0.0.0.0 --port 8000 > output.log 2>&1
                echo Aplicacion desplegada en http://localhost:8000
                """
            }
        }
    }

    post {
        always {
            echo 'Limpiando el espacio de trabajo...'
        }
        success {
            echo '¡El pipeline se completó exitosamente!'
        }
        failure {
            echo 'El pipeline falló. Revisa la consola de Jenkins.'
        }
    }
}