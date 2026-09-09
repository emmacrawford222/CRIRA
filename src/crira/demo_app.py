"""Small CRIRA web demo with customer page and admin inbox."""

from __future__ import annotations

import os
import time
from datetime import datetime
from threading import Lock
from typing import Any, Dict
from uuid import uuid4

from flask import Flask, jsonify, render_template_string, request

from crira.pipeline.analysis import analyze_review
from crira.pipeline.response import generate_response
from crira.pipeline.urgency import classify_urgency, determine_expedite_from_raw
from crira.pii.redactor import redact_review


def _to_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    return default


DEMO_MODE = _to_bool(os.getenv("DEMO_MODE"), default=True)
DEMO_POSITIVE_DELAY_SECONDS = int(
  os.getenv("DEMO_POSITIVE_DELAY_SECONDS", "30" if DEMO_MODE else "1800")
)


def create_app() -> Flask:
    app = Flask(__name__)

    review_store: Dict[str, Dict[str, Any]] = {}
    admin_inbox: list[Dict[str, Any]] = []
    lock = Lock()

    product = {
        "product_id": "prod-001",
      "name": "Airbrush Flawless Foundation",
      "description": "Long-wear liquid foundation inspired by premium studio-finish beauty lines, with buildable medium-to-full coverage.",
      "price": "£39.00",
      "image_url": "https://images.pexels.com/photos/3373747/pexels-photo-3373747.jpeg?auto=compress&cs=tinysrgb&w=1200",
      "image_backup_url": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=1200&q=80",
      "image_alt": "Foundation bottle and makeup products on a vanity table",
    }

    customer_template = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RetailGenius Demo</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Fraunces:opsz,wght@9..144,500;9..144,700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f5f1ea;
      --paper: #fffdfa;
      --ink: #1f2f2b;
      --muted: #68756f;
      --accent: #d85f36;
      --accent-soft: #f6d6c9;
      --good: #296245;
      --warn: #7f3f26;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: 'Space Grotesk', sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 18% 14%, #fce4cd 0%, transparent 40%),
        radial-gradient(circle at 84% 12%, #d9e8df 0%, transparent 38%),
        linear-gradient(135deg, #f5f1ea 0%, #f1ece4 45%, #ece7df 100%);
      display: flex;
      justify-content: center;
      padding: 28px 18px;
    }
    .wrap {
      width: 100%;
      max-width: 900px;
      background: color-mix(in srgb, var(--paper) 90%, white 10%);
      border: 1px solid #d7cdc2;
      border-radius: 20px;
      box-shadow: 0 24px 60px rgba(31, 47, 43, 0.10);
      overflow: hidden;
    }
    .head {
      padding: 20px 22px;
      border-bottom: 1px solid #e5ddd3;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }
    .brand {
      font-family: 'Fraunces', serif;
      font-size: 1.2rem;
      letter-spacing: 0.2px;
    }
    .admin-link {
      text-decoration: none;
      color: var(--ink);
      border: 1px solid #ccb9aa;
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 0.9rem;
      background: #fdf6ee;
    }
    .content {
      display: grid;
      grid-template-columns: 1fr;
      gap: 18px;
      padding: 20px;
    }
    .card {
      background: #fff;
      border: 1px solid #e6ddd4;
      border-radius: 14px;
      padding: 18px;
    }
    h1 {
      margin: 0 0 8px;
      font-family: 'Fraunces', serif;
      font-size: 2rem;
      line-height: 1.1;
    }
    .sub { color: var(--muted); margin: 0 0 12px; }
    .price {
      display: inline-block;
      background: var(--accent-soft);
      color: var(--warn);
      border-radius: 999px;
      padding: 6px 10px;
      font-weight: 700;
      font-size: 0.9rem;
    }
    .hero {
      margin-top: 14px;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid #e8dfd5;
      background: #faf6f1;
    }
    .hero img {
      width: 100%;
      height: 260px;
      object-fit: cover;
      display: block;
    }
    label { font-weight: 600; display: block; margin-bottom: 6px; }
    input, textarea {
      width: 100%;
      border: 1px solid #d8cec3;
      border-radius: 12px;
      padding: 10px 12px;
      font: inherit;
      background: #fffcf8;
    }
    textarea { min-height: 110px; resize: vertical; }
    .row {
      display: grid;
      grid-template-columns: 1fr 130px;
      gap: 10px;
      margin-bottom: 12px;
    }
    .btn {
      border: none;
      border-radius: 12px;
      padding: 11px 14px;
      font: inherit;
      font-weight: 700;
      color: #fff;
      background: var(--accent);
      cursor: pointer;
    }
    .reviews {
      margin-top: 18px;
      display: grid;
      gap: 10px;
    }
    .review-item {
      border: 1px solid #eadfce;
      background: #fffefb;
      border-radius: 12px;
      padding: 12px;
    }
    .review-head {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: center;
      margin-bottom: 6px;
      font-size: 0.92rem;
    }
    .review-name { font-weight: 700; }
    .review-rating { color: #8d4b2e; }
    .review-text { margin: 0; }
    .reply {
      margin-top: 10px;
      margin-left: 16px;
      padding: 10px 12px;
      border-left: 3px solid #d8c2ad;
      background: #faf5ef;
      border-radius: 8px;
      display: none;
    }
    .reply-title {
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.4px;
      color: #7b6b5f;
      margin-bottom: 4px;
      font-weight: 700;
    }
    .empty-reviews {
      color: var(--muted);
      border: 1px dashed #d9cfc4;
      border-radius: 10px;
      padding: 12px;
      background: #fffdf9;
    }
    .meta { color: var(--muted); font-size: 0.9rem; }
    @media (max-width: 700px) {
      .row { grid-template-columns: 1fr; }
      h1 { font-size: 1.6rem; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="head">
      <div class="brand">RetailGenius CRIRA Demo</div>
      <a class="admin-link" href="/admin">Open Admin Inbox</a>
    </div>
    <div class="content">
      <section class="card">
        <figure class="hero">
          <img id="product-hero-img" src="{{ product_image_url }}" alt="{{ product_image_alt }}" loading="lazy" />
        </figure>
        <h1 style="margin-top:14px;">{{ product_name }}</h1>
        <p class="sub">{{ product_desc }}</p>
        <span class="price">{{ product_price }}</span>
      </section>

      <section class="card">
        <h2>Customer Reviews</h2>
        <p class="sub">Newest reviews appear first. Business replies are shown underneath each review.</p>
        <div id="empty-reviews" class="empty-reviews">No reviews yet. Be the first to post.</div>
        <div id="reviews" class="reviews"></div>
      </section>

      <section class="card">
        <h2>Leave A Review</h2>
        <p class="sub">Share your experience below. Your review will appear in the customer list above.</p>
        <form id="review-form">
          <div class="row">
            <div>
              <label for="customer_name">Name (optional)</label>
              <input id="customer_name" name="customer_name" placeholder="Taylor" />
            </div>
            <div>
              <label for="rating">Rating</label>
              <input id="rating" name="rating" type="number" min="1" max="5" value="5" />
            </div>
          </div>
          <div>
            <label for="review_text">Review</label>
            <textarea id="review_text" name="review_text" placeholder="Tell us what happened..."></textarea>
          </div>
          <div style="margin-top:12px; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
            <button class="btn" type="submit">Send Review</button>
            <span class="meta">Business replies may appear shortly after posting.</span>
          </div>
        </form>
      </section>
    </div>
  </div>

  <script>
    const form = document.getElementById('review-form');
    const reviewsBox = document.getElementById('reviews');
    const emptyReviews = document.getElementById('empty-reviews');
    const heroImg = document.getElementById('product-hero-img');
    const backupImage = {{ product_image_backup_url|tojson }};
    const pollingByReviewId = new Map();

    heroImg.addEventListener('error', () => {
      if (heroImg.dataset.fallbackApplied === '1') {
        heroImg.src = 'https://picsum.photos/1200/800?grayscale&blur=1';
        return;
      }
      heroImg.dataset.fallbackApplied = '1';
      heroImg.src = backupImage;
    });

    function addReviewToList(reviewId, name, rating, reviewText) {
      emptyReviews.style.display = 'none';
      const item = document.createElement('article');
      item.className = 'review-item';
      item.id = `review-${reviewId}`;
      item.innerHTML = `
        <div class="review-head">
          <span class="review-name">${name || 'Verified Customer'}</span>
          <span class="review-rating">${'★'.repeat(Math.max(1, Math.min(5, rating || 5)))} </span>
        </div>
        <p class="review-text">${reviewText}</p>
        <div class="reply" id="reply-${reviewId}">
          <div class="reply-title">Response from business</div>
          <div id="reply-text-${reviewId}"></div>
        </div>
      `;
      reviewsBox.prepend(item);
    }

    function applyReply(reviewId, replyText) {
      if (!replyText) {
        return;
      }
      const reply = document.getElementById(`reply-${reviewId}`);
      const replyTextNode = document.getElementById(`reply-text-${reviewId}`);
      if (!reply || !replyTextNode) {
        return;
      }
      replyTextNode.textContent = replyText;
      reply.style.display = 'block';
    }

    async function pollStatus(reviewId) {
      try {
        const res = await fetch(`/api/reviews/${reviewId}`);
        const data = await res.json();
        if (data.response) {
          applyReply(reviewId, data.response);
        }
        if (data.state === 'completed' || data.state === 'human_review') {
          const timerId = pollingByReviewId.get(reviewId);
          if (timerId) {
            clearInterval(timerId);
            pollingByReviewId.delete(reviewId);
          }
        }
      } catch (err) {
        console.error(err);
      }
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();

      const customerName = document.getElementById('customer_name').value;
      const rating = Number(document.getElementById('rating').value || 5);
      const reviewText = document.getElementById('review_text').value;
      const payload = {
        customer_name: customerName,
        rating: rating,
        review_text: reviewText
      };

      const res = await fetch('/api/reviews', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (data.review_id) {
        addReviewToList(data.review_id, customerName, rating, reviewText);
        const timerId = setInterval(() => pollStatus(data.review_id), 1200);
        pollingByReviewId.set(data.review_id, timerId);
        if (data.response) {
          applyReply(data.review_id, data.response);
        }
      }

      form.reset();
      document.getElementById('rating').value = 5;
    });
  </script>
</body>
</html>
"""

    admin_template = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CRIRA Admin Inbox</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f3f6f4;
      --card: #ffffff;
      --ink: #12231d;
      --muted: #617069;
      --line: #d8e2dd;
      --accent: #245b45;
    }
    body {
      margin: 0;
      font-family: 'Space Grotesk', sans-serif;
      background: linear-gradient(160deg, #edf5f0 0%, #f8faf8 100%);
      color: var(--ink);
      padding: 20px;
    }
    .top {
      max-width: 980px;
      margin: 0 auto 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
    }
    .link { color: var(--accent); text-decoration: none; font-weight: 700; }
    .stack {
      max-width: 980px;
      margin: 0 auto;
      display: grid;
      gap: 12px;
    }
    .item {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
    }
    .meta { color: var(--muted); font-size: 0.92rem; }
    .badge {
      display: inline-block;
      background: #e4efe9;
      color: #225640;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
      padding: 4px 8px;
      margin-right: 6px;
      text-transform: uppercase;
    }
    .empty {
      background: #fff;
      border: 1px dashed #cdd8d2;
      border-radius: 12px;
      padding: 16px;
      color: var(--muted);
    }
  </style>
</head>
<body>
  <div class="top">
    <h1>Human Review Inbox</h1>
    <a href="/" class="link">Back to product page</a>
  </div>
  <div class="stack">
    {% if items|length == 0 %}
      <div class="empty">No escalated reviews yet.</div>
    {% else %}
      {% for item in items %}
        <article class="item">
          <div style="margin-bottom:6px;">
            <span class="badge">{{ item.route }}</span>
            <span class="badge">internal support</span>
          </div>
          <div><strong>Review ID:</strong> {{ item.review_id }}</div>
          <div><strong>Reason:</strong> {{ item.reason }}</div>
          <div><strong>Tone:</strong> {{ item.tone }}</div>
          <div><strong>Redacted review:</strong> {{ item.redacted_review }}</div>
          <div class="meta">Created: {{ item.created_at }}</div>
          <div style="margin-top:8px;"><strong>Draft response preview:</strong> {{ item.response_preview }}</div>
        </article>
      {% endfor %}
    {% endif %}
  </div>
</body>
</html>
"""

    def _process_review(payload: Dict[str, Any]) -> Dict[str, Any]:
        review_text = str(payload.get("review_text", "")).strip()
        if not review_text:
            raise ValueError("review_text is required")

        rating = payload.get("rating", 5)
        try:
            rating = int(rating)
        except Exception:
            rating = 5

        review = {
            "review_id": payload.get("review_id") or f"demo-{uuid4().hex[:8]}",
            "date": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "customer_name": str(payload.get("customer_name", "") or ""),
            "rating": rating,
            "review_text": review_text,
        }

        expedite_gate = determine_expedite_from_raw(review_text=review["review_text"], rating=rating)
        redacted_review = redact_review(review)
        redacted_review["expedite"] = expedite_gate["expedite"]

        analysis = analyze_review(redacted_review)
        urgency_input = {
            "sentiment": analysis.get("sentiment"),
            "tone": analysis.get("tone"),
            "expedite": analysis.get("expedite", False),
            "rating": rating,
            "rating_signals": analysis.get("rating_signals"),
            "main_points": analysis.get("main_points", []),
        }
        urgency = classify_urgency(urgency_input)
        response = generate_response(redacted_review.get("review_text", ""), analysis=analysis, urgency=urgency)

        route = str(urgency.get("route", "llm_response"))
        tone = str(analysis.get("tone", "neutral"))
        state = "completed"
        available_at = time.time()

        if route == "human_review":
            state = "human_review"
        elif route == "llm_response" and tone == "positive":
            state = "waiting_delay"
            available_at = time.time() + DEMO_POSITIVE_DELAY_SECONDS

        return {
            "review_id": review["review_id"],
            "created_at": review["date"],
            "raw_review": review,
            "redacted_review": redacted_review.get("review_text", ""),
            "analysis": analysis,
            "urgency": urgency,
            "route": route,
            "tone": tone,
            "internal_support_flag": bool(urgency.get("is_urgent") or route == "human_review"),
            "state": state,
            "response": response,
            "available_at": available_at,
        }

    def _to_public_status(record: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()
        state = record.get("state", "completed")
        response = record.get("response", "")
        pending_seconds = None

        if state == "waiting_delay":
            wait_left = int(max(0, record.get("available_at", now) - now))
            pending_seconds = wait_left
            if wait_left > 0:
                response = ""
            else:
                state = "completed"

        return {
            "review_id": record.get("review_id"),
            "state": state,
            "route": record.get("route"),
            "tone": record.get("tone"),
            "internal_support_flag": record.get("internal_support_flag"),
            "reason": record.get("urgency", {}).get("reason", ""),
            "response": response,
            "pending_seconds": pending_seconds,
        }

    @app.get("/")
    def customer_page():
        return render_template_string(
            customer_template,
            product_name=product["name"],
            product_desc=product["description"],
            product_price=product["price"],
            product_image_url=product["image_url"],
            product_image_backup_url=product["image_backup_url"],
            product_image_alt=product["image_alt"],
            delay_seconds=DEMO_POSITIVE_DELAY_SECONDS,
        )

    @app.get("/admin")
    def admin_page():
        with lock:
            items = list(reversed(admin_inbox))
        return render_template_string(admin_template, items=items)

    @app.post("/api/reviews")
    def submit_review():
        payload = request.get_json(silent=True) or {}
        try:
            record = _process_review(payload)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        with lock:
            review_store[record["review_id"]] = record
            if record["route"] == "human_review":
                admin_inbox.append(
                    {
                        "review_id": record["review_id"],
                        "created_at": record["created_at"],
                        "reason": record["urgency"].get("reason", ""),
                        "route": record["route"],
                        "tone": record["tone"],
                        "redacted_review": record["redacted_review"],
                        "response_preview": record["response"],
                    }
                )

        return jsonify(_to_public_status(record))

    @app.get("/api/reviews/<review_id>")
    def get_review_status(review_id: str):
        with lock:
            record = review_store.get(review_id)
            if record is None:
                return jsonify({"error": "review not found"}), 404

            if record.get("state") == "waiting_delay" and time.time() >= record.get("available_at", 0):
                record["state"] = "completed"

            status = _to_public_status(record)

        return jsonify(status)

    return app


def main() -> None:
    app = create_app()
    host = os.getenv("DEMO_HOST", "127.0.0.1")
    port = int(os.getenv("DEMO_PORT", "8080"))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
