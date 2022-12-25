import scrapy
from pathlib import Path

from scrapy import FormRequest
from scrapy.crawler import CrawlerProcess
from scrapy.shell import inspect_response
from scrapy.exporters import JsonLinesItemExporter
import json
from scrapy.utils.project import get_project_settings
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
import re

NEXT_LINE_PATTERN = re.compile(r"\n{1,}")


class ReviewsItem(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    review_header = scrapy.Field()
    review_content = scrapy.Field()
    language = scrapy.Field()
    rating = scrapy.Field()
    max_rating = scrapy.Field()
    helpful_review = scrapy.Field()


class TitleCleaner:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if adapter.get("title"):
            adapter["title"] = (
                adapter["title"].split("Review of")[-1].split("- IMDb")[0].strip()
            )
            adapter["title"] = re.sub(NEXT_LINE_PATTERN, "", adapter["title"])
        else:
            adapter["title"] = ""
        return item


class ReviewHeaderCleaner:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if adapter.get("review_header"):
            adapter["review_header"] = adapter["review_header"].strip()
            adapter["review_header"] = re.sub(
                NEXT_LINE_PATTERN, "", adapter["review_header"]
            )
        else:
            adapter["review_header"] = ""
        return item


class ReviewContentHeader:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if adapter.get("review_content"):
            adapter["review_content"] = adapter["review_content"].strip()
            adapter["review_content"] = re.sub(
                NEXT_LINE_PATTERN, "", adapter["review_content"]
            )
        else:
            adapter["review_content"] = ""
        return item


class MaxRatingCleaner:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if adapter.get("max_rating"):
            adapter["max_rating"] = adapter["max_rating"].strip("/").strip()
            adapter["max_rating"] = re.sub(NEXT_LINE_PATTERN, "", adapter["max_rating"])
        else:
            adapter["max_rating"] = ""
        return item


class HelpfulReviewCleaner:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if isinstance(adapter.get("helpful_review"), str):
            if "out of" in adapter["helpful_review"]:
                adapter["helpful_review"] = (
                    adapter["helpful_review"]
                    .split("found")[0]
                    .strip()
                    .replace("out of", "/")
                )
                adapter["helpful_review"] = re.sub(
                    NEXT_LINE_PATTERN, "", adapter["helpful_review"]
                )
        else:
            adapter["helpful_review"] = ""
        return item


class ReviewStore:
    def open_spider(self, spider):
        # make raw folder to save the data
        file_path = Path(__file__).resolve().parent
        raw_folder = file_path / "data"
        raw_folder.mkdir(exist_ok=True, parents=True)
        spider.logger.info("Data folder created...")

        self.file = open(str(raw_folder / "reviews.json"), "wb")
        self.exporter = JsonLinesItemExporter(self.file, ensure_ascii=True)
        self.exporter.start_exporting()

    def close_spider(self, spider):
        self.exporter.finish_exporting()
        self.file.close()

    def process_item(self, item, spider):
        self.exporter.export_item(item)
        return item


class Reviews(scrapy.Spider):
    def __init__(self):
        self.IMDB_HOST_URL = "https://www.imdb.com"
        self.MOVIES_CODE = ["tt7657566", "tt7991608"]
        self.REVIEW_PAGES = 3

    def start_requests(self):
        # made response to the individual movie home page
        for code in self.MOVIES_CODE:
            yield FormRequest(
                method="GET",
                url=f"{self.IMDB_HOST_URL}/title/{code}/reviews",
                formdata={"ref_": "tt_urv"},
                callback=self.parse,
                meta={"code": code},
            )

    def parse(self, response, **kwargs):
        # get the pagination key for every movie pages
        pagination_key = response.css(
            "div[class='load-more-data'] ::attr('data-key')"
        ).get()
        # make request to load more reviews
        yield FormRequest(
            method="GET",
            url=f"{self.IMDB_HOST_URL}/title/{response.meta['code']}/reviews/_ajax",
            formdata={"ref_": "undefined", "paginationKey": pagination_key},
            callback=self.next_page_reviews,
            meta={"page": 1, "code": response.meta["code"], "reviews_link": []},
        )

    def next_page_reviews(self, response):
        # collect all the links for every review
        # then make request to load more reviews
        if response.meta["page"] < self.REVIEW_PAGES:
            # get all the links for reviews
            all_links = response.css("a[class='title']::attr(href)").getall()
            # add them to meta dictionary
            response.meta["reviews_link"].extend(all_links)
            # made request to reload page
            pagination_key = response.css(
                "div[class='load-more-data'] ::attr('data-key')"
            ).get()
            yield FormRequest(
                method="GET",
                url=f"{self.IMDB_HOST_URL}/title/{response.meta['code']}/reviews/_ajax",
                formdata={"ref_": "undefined", "paginationKey": pagination_key},
                callback=self.next_page_reviews,
                meta={
                    "page": response.meta["page"] + 1,
                    "code": response.meta["code"],
                    "reviews_link": response.meta["reviews_link"],
                },
            )

        # for all the links collected make request to review page
        else:
            for review_link in response.meta["reviews_link"]:
                # laod more pages with nex
                yield FormRequest(
                    method="GET",
                    url=f"{self.IMDB_HOST_URL}{review_link}",
                    callback=self.review_page,
                    meta={
                        "code": response.meta["code"],
                    },
                )

    def review_page(self, response):
        # inspect_response(response, self)
        review_schema = json.loads(
            response.css("script[type='application/ld+json']::text").get()
        )
        yield {
            "url": response.request.url,
            "title": response.css("title::text").get(),
            "review_header": response.css("a[class='title']::text").get(),
            "review_content": review_schema["reviewBody"]
            if "reviewBody" in review_schema
            else ".".join(
                response.css("div[class='text show-more__control']::text").getall()
            ),
            "language": review_schema.get("inLanguage"),
            "rating": response.css(
                "span[class='rating-other-user-rating'] > span::text"
            ).get(),
            "max_rating": response.css(
                "span[class='rating-other-user-rating'] > span[class='point-scale']::text"
            ).get(),
            "helpful_review": response.css(
                "div[class='actions text-muted']::text"
            ).get(),
        }


def main():

    settings = get_project_settings()
    settings.set("CUSTOM_SETTING", "Super Custom Setting")
    settings.update(
        {
            "ITEM_PIPELINES": {
                TitleCleaner: 10,
                ReviewHeaderCleaner: 15,
                ReviewContentHeader: 20,
                MaxRatingCleaner: 25,
                HelpfulReviewCleaner: 30,
                ReviewStore: 35,
            }
        }
    )

    process = CrawlerProcess(settings)
    process.crawl(Reviews)
    process.start()


if __name__ == "__main__":
    main()
