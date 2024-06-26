import os
from typing import List

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.future import select
from sqlalchemy.orm import Session

from src.classifier import Classifier
from src.db import models
from src.db.database import Database
from src.db.models import Result
from src.preprocessor import Preprocessor
from src.settings.classifier import PredictOutput
from src.settings.config import AppConfig
from src.settings.db import DBResult
from src.settings.preprocessor import PreprocessorSettings
from src.utils import load_config

load_dotenv()


app = FastAPI()
db = Database(os.getenv("DATABASE_URL"))

@app.on_event("startup")
def startup_event():
    config: AppConfig = load_config()
    assert os.path.isdir(config.load_path), "There is no model dir"
    app.state.preprocessor_settings = PreprocessorSettings(**config.preprocessing_config.dict())
    app.state.preprocessor = Preprocessor(settings=app.state.preprocessor_settings)
    app.state.classifier = Classifier.load(config.load_path)
    
    db.create_tables()

@app.get("/")
def index():
    return {"index": "classification app working"}


@app.get("/results", status_code=200, response_model=List[DBResult])
def read_results(db_session: Session = Depends(db.get_db)):
    query = select(Result)
    result = db_session.execute(query)
    results = result.scalars().all()
    return results


@app.post("/classify/{message}", status_code=200, response_model=PredictOutput)
def classify_input(message: str, db_session: Session = Depends(db.get_db)):
    try:
        processed_test: str = app.state.preprocessor(message)
        pred: PredictOutput = app.state.classifier.predict(processed_test)
        result = models.Result(message=message, sentiment=pred.sentiment)
        db_session.add(result)
        db_session.commit()
        return pred
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")
