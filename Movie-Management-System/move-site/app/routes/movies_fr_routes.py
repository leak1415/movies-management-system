from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
)
from ..extensions import db
from ..models.movie import Movie
import os
from werkzeug.utils import secure_filename
import requests

# -----------------------------
# Blueprint
# -----------------------------
movie_fr_bp = Blueprint("movie_fr_bp", __name__, url_prefix="/")

# -----------------------------
# Allowed file extensions
# -----------------------------
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "ogg"}


def allowed_image_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def allowed_video_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS
    )


# -----------------------------
# Routes
# -----------------------------


# Home page
@movie_fr_bp.route("/")
def home():
    movies = Movie.query.all()
    return render_template("index.html", movies=movies)


# About page
@movie_fr_bp.route("/about")
def about():
    return render_template("about-us.html")


# List movies
@movie_fr_bp.route("/list_movies")
def list_movies():
    movies = Movie.query.all()
    return render_template("list-movies.html", movies=movies)


# Add movie
@movie_fr_bp.route("/add_movie", methods=["GET", "POST"])
def add_movie():
    if request.method == "POST":
        movie_name = request.form.get("movie_name")
        type_ = request.form.get("type")
        price = request.form.get("price")
        quality = request.form.get("quality")
        rating = request.form.get("rating")
        year = request.form.get("year")
        director = request.form.get("director")
        role = request.form.get("role")
        time_watching = request.form.get("time_watching")
        hall_name = request.form.get("hall_name")
        chair_number = request.form.get("chair_number")
        trailer_url = request.form.get("trailer_url")  # Optional YouTube link

        if not all([movie_name, type_, price, quality]):
            flash("Title, Type, Price, and Quality are required!")
            return redirect(url_for("movie_fr_bp.add_movie"))

        try:
            price = float(price)
            rating = float(rating) if rating else None
            year = int(year) if year else None
            time_watching = int(time_watching) if time_watching else None
            chair_number = int(chair_number) if chair_number else None
        except ValueError:
            flash(
                "Price, Rating, Year, Time Watching, and Chair Number must be numbers."
            )
            return redirect(url_for("movie_fr_bp.add_movie"))

        new_movie = Movie(
            movie_name=movie_name,
            type=type_,
            price=price,
            quality=quality,
            rating=rating,
            year=year,
            director=director,
            role=role,
            time_watching=time_watching,
            hall_name=hall_name,
            chair_number=chair_number,
            trailer_url=trailer_url,
        )

        db.session.add(new_movie)
        db.session.commit()
        flash("Movie added successfully!")
        return redirect(url_for("movie_fr_bp.list_movies"))

    return render_template("add-movie.html", movie={})


# Edit movie
@movie_fr_bp.route("/edit_movie/<int:movie_id>", methods=["GET", "POST"])
def edit_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    if request.method == "POST":
        movie.movie_name = request.form.get("movie_name")
        movie.type = request.form.get("type")
        movie.quality = request.form.get("quality")
        movie.trailer_url = request.form.get("trailer_url")

        try:
            movie.price = float(request.form.get("price"))
            movie.rating = (
                float(request.form.get("rating"))
                if request.form.get("rating")
                else None
            )
            movie.year = (
                int(request.form.get("year")) if request.form.get("year") else None
            )
            movie.time_watching = (
                int(request.form.get("time_watching"))
                if request.form.get("time_watching")
                else None
            )
            movie.chair_number = (
                int(request.form.get("chair_number"))
                if request.form.get("chair_number")
                else None
            )
        except ValueError:
            flash(
                "Price, Rating, Year, Time Watching, and Chair Number must be numbers."
            )
            return redirect(url_for("movie_fr_bp.edit_movie", movie_id=movie_id))

        movie.director = request.form.get("director")
        movie.role = request.form.get("role")
        movie.hall_name = request.form.get("hall_name")

        db.session.commit()
        flash("Movie updated successfully!")
        return redirect(url_for("movie_fr_bp.view_movie", movie_id=movie_id))

    return render_template("edit-movie.html", movie=movie)


# Delete movie
@movie_fr_bp.route("/delete_movie/<int:movie_id>", methods=["POST"])
def delete_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    db.session.delete(movie)
    db.session.commit()
    flash("Movie deleted successfully!")
    return redirect(url_for("movie_fr_bp.list_movies"))


# Search movies
@movie_fr_bp.route("/movies/search")
def search_movies():
    query = request.args.get("q", "").strip()
    if query:
        movies = Movie.query.filter(Movie.movie_name.ilike(f"%{query}%")).all()
    else:
        movies = Movie.query.all()
    return render_template("list-movies.html", movies=movies)


# Filter by type
@movie_fr_bp.route("/movies/type/<type_name>")
def filter_by_type(type_name):
    movies = Movie.query.filter_by(type=type_name).all()
    return render_template("list-movies.html", movies=movies)


# View movie details
@movie_fr_bp.route("/view_movie/<int:movie_id>")
def view_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    return render_template("view-movie.html", movie=movie)


# Fetch details from OMDb and update missing fields
@movie_fr_bp.route("/movies/<int:movie_id>/fetch-details", methods=["POST"])
def fetch_details(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    api_key = current_app.config.get("OMDB_API_KEY") or os.environ.get("OMDB_API_KEY")
    if not api_key:
        flash("OMDb API key not configured. Set OMDB_API_KEY in environment or app config.")
        return redirect(url_for("movie_fr_bp.view_movie", movie_id=movie_id))

    params = {"t": movie.movie_name, "apikey": api_key}
    if movie.year:
        params["y"] = movie.year

    try:
        resp = requests.get("https://www.omdbapi.com/", params=params, timeout=10)
        data = resp.json()
        if data.get("Response") == "True":
            # Only fill fields that are currently missing
            year_val = data.get("Year")
            if movie.year is None and year_val and year_val.isdigit():
                movie.year = int(year_val)

            imdb_rating = data.get("imdbRating")
            if movie.rating is None and imdb_rating and imdb_rating != "N/A":
                try:
                    movie.rating = float(imdb_rating)
                except ValueError:
                    pass

            director_val = data.get("Director")
            if (not movie.director) and director_val and director_val != "N/A":
                movie.director = director_val

            actors_val = data.get("Actors")
            if (not movie.role) and actors_val and actors_val != "N/A":
                movie.role = actors_val

            runtime_val = data.get("Runtime")  # e.g., '123 min'
            if movie.time_watching is None and runtime_val and runtime_val.endswith("min"):
                parts = runtime_val.split()
                if parts and parts[0].isdigit():
                    movie.time_watching = int(parts[0])

            db.session.commit()
            flash("Details fetched and updated from OMDb.")
        else:
            flash("No details found from OMDb for this title.")
    except Exception:
        flash("Failed to fetch details from OMDb.")

    return redirect(url_for("movie_fr_bp.view_movie", movie_id=movie_id))


# -----------------------------
# Image Upload
# -----------------------------
@movie_fr_bp.route("/movies/<int:movie_id>/upload-image", methods=["POST"])
def upload_image(movie_id):
    file = request.files.get("image")
    if not file or file.filename == "":
        flash("No image selected")
        return redirect(url_for("movie_fr_bp.view_movie", movie_id=movie_id))

    if not allowed_image_file(file.filename):
        flash("Invalid image type. Allowed: " + ", ".join(ALLOWED_IMAGE_EXTENSIONS))
        return redirect(url_for("movie_fr_bp.view_movie", movie_id=movie_id))

    filename = secure_filename(file.filename)
    upload_folder = os.path.join(current_app.static_folder, "images")
    os.makedirs(upload_folder, exist_ok=True)

    # Prefix with movie_id to avoid overwriting
    name, ext = os.path.splitext(filename)
    filename = f"{movie_id}_{name}{ext}"
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    movie = Movie.query.get(movie_id)
    if movie:
        if movie.image and movie.image != filename:
            old_path = os.path.join(upload_folder, movie.image)
            if os.path.exists(old_path):
                os.remove(old_path)
        movie.image = filename
        db.session.commit()

    flash("Image uploaded successfully")
    return redirect(url_for("movie_fr_bp.view_movie", movie_id=movie_id))


# -----------------------------
# Trailer Upload
# -----------------------------
@movie_fr_bp.route("/movies/<int:movie_id>/upload-trailer", methods=["POST"])
def upload_trailer(movie_id):
    file = request.files.get("trailer_file")
    if not file or file.filename == "":
        flash("No trailer selected")
        return redirect(url_for("movie_fr_bp.view_movie", movie_id=movie_id))

    if not allowed_video_file(file.filename):
        flash("Invalid video type. Allowed: " + ", ".join(ALLOWED_VIDEO_EXTENSIONS))
        return redirect(url_for("movie_fr_bp.view_movie", movie_id=movie_id))

    filename = secure_filename(file.filename)
    upload_folder = os.path.join(current_app.static_folder, "trailers")
    os.makedirs(upload_folder, exist_ok=True)

    # Prefix with movie_id to avoid overwriting
    name, ext = os.path.splitext(filename)
    filename = f"{movie_id}_{name}{ext}"
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    movie = Movie.query.get(movie_id)
    if movie:
        if movie.trailer_file and movie.trailer_file != filename:
            old_path = os.path.join(upload_folder, movie.trailer_file)
            if os.path.exists(old_path):
                os.remove(old_path)
        movie.trailer_file = filename
        db.session.commit()

    flash("Trailer uploaded successfully")
    return redirect(url_for("movie_fr_bp.view_movie", movie_id=movie_id))
