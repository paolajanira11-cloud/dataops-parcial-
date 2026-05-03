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
                sh """
                python3 -m venv $PYTHON_ENV
                . $PYTHON_ENV/bin/activate
                pip install -r requirements.txt
                """
            }
        }

        stage('Static Analysis & Linting') {
            steps {
                sh """
                . $PYTHON_ENV/bin/activate
                pip install flake8
                flake8 . --exclude=$PYTHON_ENV --count --select=E9,F63,F7,F82 --show-source --statistics
                """
            }
        }

        stage('Run Tests') {
            steps {
                sh """
                . $PYTHON_ENV/bin/activate
                pip install pytest
                pytest
                """
            }
        }

        stage('Deploy (Local)') {
            steps {
                sh """
                . $PYTHON_ENV/bin/activate
                pkill uvicorn || true
                nohup uvicorn main:app --host 0.0.0.0 --port 8000 > output.log 2>&1 &
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
            echo 'El pipeline falló. Revisa los logs.'
        }
    }
}