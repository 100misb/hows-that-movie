### Setting up Project
- Setting up virtual environment, all the required libraries dependencies are present inside `requirements.txt`.
    ```
    pip3 install -r requirements.txt
    ```

### Scraping movie reviews from IMDb : 
- Get movie code from IMDb website (usually present in the Movie page URL)
- Collect 20 such URL's and put them inside as entries for `self.MOVIES_CODE` present inside `reviews_scraper.py`.
- Run the scraper with the following command :
 
    ```
    python3 reviews_scraper.py
    ```
- Data will be collected and stored inside `data/reviews.json`
- Following fields are scraped during the process of scraping : 

|Attribute|Description|
|:-|:-|
|url|Link to the review page|
|title|Movie name for which the review is about|
|review_header|Title / Subject for the review|
|review_content|Detail Description for the review|
|language|Language in which review is written|
|rating|Rating of the movie given by reviewer|
|max_rating|Max value of rating|
|helpful_review|How many people find the review helpful v/s total|