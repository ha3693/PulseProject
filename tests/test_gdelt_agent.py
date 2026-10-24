"""Unit and integration tests for GDELT DOC 2.0 API Agent and Client."""

import os
import shutil
import tempfile
import unittest
from datetime import datetime
from agents.gdelt.client import GdeltDocClient
from agents.gdelt.agent import GdeltAgent
from agents import get_agent
from agents.schemas import SignalReport, PostItem


class TestGdeltAgent(unittest.TestCase):
    """Test suite covering GDELT client normalization, mock data, and agent execution."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_agent_factory(self):
        """Verify factory returns GdeltAgent instances for aliases."""
        agent = get_agent("gdelt")
        self.assertIsInstance(agent, GdeltAgent)

        agent_doc = get_agent("gdelt-doc")
        self.assertIsInstance(agent_doc, GdeltAgent)

        agent_news = get_agent("gdelt_news")
        self.assertIsInstance(agent_news, GdeltAgent)

    def test_client_normalization(self):
        """Verify that raw GDELT DOC article dictionary normalizes to Pulse schema."""
        client = GdeltDocClient()
        raw_article = {
            "url": "https://www.reuters.com/technology/test-article-123",
            "title": "Nvidia unveils next-generation AI chip architecture",
            "seendate": "20261023T153000Z",
            "domain": "reuters.com",
            "sourcecountry": "US",
            "language": "English",
            "socialimage": "https://images.reuters.com/nvda.jpg",
        }

        item = client._normalize_article(raw_article)

        self.assertTrue(item["id"].startswith("gdelt_"))
        self.assertEqual(item["subreddit"], "reuters.com")
        self.assertEqual(item["title"], raw_article["title"])
        self.assertEqual(item["url"], raw_article["url"])
        self.assertEqual(item["score"], 10)
        self.assertEqual(item["num_comments"], 0)
        self.assertEqual(item["upvote_ratio"], 1.0)
        self.assertIn("reuters.com", item["content_text"])

        # Verify Pydantic PostItem compatibility
        post = PostItem(
            id=item["id"],
            subreddit=item["subreddit"],
            title=item["title"],
            url=item["url"],
            permalink=item["permalink"],
            published_at=item["published_at"],
            score=item["score"],
            content_text=item["content_text"],
            is_relevant=True,
        )
        self.assertEqual(post.id, item["id"])

    def test_client_mock_articles(self):
        """Verify mock news generator returns properly structured articles for a topic."""
        client = GdeltDocClient()
        articles = client.search_articles(query="Quantum Computing", limit=5, use_mock=True)

        self.assertEqual(len(articles), 5)
        for a in articles:
            self.assertTrue(
                "Quantum Computing" in a["title"] or "Quantum Computing" in a["content_text"]
            )
            self.assertTrue(a["url"].startswith("http"))
            self.assertIn(
                a["subreddit"],
                [
                    "reuters.com",
                    "bloomberg.com",
                    "ft.com",
                    "wsj.com",
                    "cnbc.com",
                    "marketwatch.com",
                    "apnews.com",
                    "barrons.com",
                ],
            )

    def test_agent_run_mock(self):
        """Verify end-to-end agent run returns valid SignalReport schema."""
        out_file = os.path.join(self.test_dir, "test_gdelt_report.json")
        agent = GdeltAgent(output_dir=self.test_dir)

        report = agent.run(
            topic="Semiconductors",
            time_window="day",
            limit=5,
            output_file=out_file,
            use_mock=True,
        )

        self.assertEqual(report["topic"], "Semiconductors")
        self.assertTrue(-100.0 <= report["aggregate_sentiment_score"] <= 100.0)
        self.assertIn("positive", report["sentiment_breakdown"])
        self.assertEqual(len(report["posts"]), 5)
        self.assertTrue(len(report["top_themes"]) > 0)
        self.assertTrue(os.path.exists(out_file))

        # Validate against SignalReport pydantic schema
        validated = SignalReport(**report)
        self.assertEqual(validated.topic, "Semiconductors")
        self.assertEqual(len(validated.posts), 5)


if __name__ == "__main__":
    unittest.main()
