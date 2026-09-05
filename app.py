import sqlite3
from flask import Flask, render_template, request, jsonify, g, redirect, url_for

app = Flask(__name__)
DATABASE = 'movies.db'

# ============================================
# DATABASE FUNCTIONS
# ============================================

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create movies table with UNIQUE constraint
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year INTEGER NOT NULL,
            genre TEXT NOT NULL,
            rating REAL,
            director TEXT,
            UNIQUE(title, year, director)
        )
    ''')
    
    # Check if data exists
    cursor.execute("SELECT COUNT(*) FROM movies")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("📀 Seeding database...")
        from movies_data import MOVIES
        cursor.executemany(
            "INSERT INTO movies (title, year, genre, rating, director) VALUES (?, ?, ?, ?, ?)",
            MOVIES
        )
        conn.commit()
        print(f"✅ Added {len(MOVIES)} movies")
    else:
        print(f"✅ Database has {count} movies")
    
    conn.close()

def get_distinct_genres():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT DISTINCT genre FROM movies ORDER BY genre")
    return [row['genre'] for row in cursor.fetchall()]

def get_total_movie_count():
    """Get total number of movies in database"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM movies")
    return cursor.fetchone()[0]

# ============================================
# DUPLICATE CHECK FUNCTION
# ============================================

def check_duplicate_movie(title, year, director=None, exclude_id=None):
    """Check if a movie with same title, year, and director already exists"""
    db = get_db()
    cursor = db.cursor()
    
    query = "SELECT id, title, year, director FROM movies WHERE title = ? AND year = ?"
    params = [title.strip(), year]
    
    if director:
        query += " AND director = ?"
        params.append(director.strip())
    else:
        query += " AND (director IS NULL OR director = '')"
    
    if exclude_id:
        query += " AND id != ?"
        params.append(exclude_id)
    
    cursor.execute(query, params)
    result = cursor.fetchone()
    
    if result:
        return dict(result)
    return None

# ============================================
# SQL QUERY BUILDER
# ============================================

def build_search_query(params, include_count=False):
    base = "SELECT * FROM movies"
    where = []
    values = []
    
    q = params.get('q', '').strip()
    if q:
        where.append("title LIKE ?")
        values.append(f"%{q}%")
    
    genre = params.get('genre', 'All')
    if genre and genre != 'All':
        where.append("genre = ?")
        values.append(genre)
    
    year_min = params.get('year_min')
    if year_min and year_min.isdigit():
        where.append("year >= ?")
        values.append(int(year_min))
    
    year_max = params.get('year_max')
    if year_max and year_max.isdigit():
        where.append("year <= ?")
        values.append(int(year_max))
    
    rating_min = params.get('rating_min')
    if rating_min:
        try:
            r = float(rating_min)
            if 0 <= r <= 10:
                where.append("rating >= ?")
                values.append(r)
        except ValueError:
            pass
    
    where_clause = ""
    if where:
        where_clause = " WHERE " + " AND ".join(where)
        query = base + where_clause
    else:
        query = base
    
    total_count = 0
    if include_count:
        count_query = "SELECT COUNT(*) FROM movies" + where_clause
        db = get_db()
        cursor = db.cursor()
        cursor.execute(count_query, values)
        total_count = cursor.fetchone()[0]
    
    sort_map = {
        'rating_desc': 'rating DESC',
        'rating_asc': 'rating ASC',
        'year_desc': 'year DESC',
        'year_asc': 'year ASC',
        'title_asc': 'title ASC'
    }
    sort = params.get('sort', 'rating_desc')
    if sort in sort_map:
        query += " ORDER BY " + sort_map[sort]
    
    query += " LIMIT 50"
    
    return query, values, total_count

# ============================================
# ADVANCED ANALYTICS - NEW ENDPOINTS
# ============================================

@app.route('/api/analytics/rating-distribution')
def get_rating_distribution():
    """Get rating distribution histogram data"""
    db = get_db()
    cursor = db.cursor()
    
    # Get rating distribution in 0.5 increments
    cursor.execute("""
        SELECT 
            ROUND(rating * 2) / 2 as rating_bucket,
            COUNT(*) as count
        FROM movies 
        WHERE rating IS NOT NULL
        GROUP BY rating_bucket
        ORDER BY rating_bucket
    """)
    
    data = [dict(row) for row in cursor.fetchall()]
    return jsonify(data)

@app.route('/api/analytics/top-directors')
def get_top_directors():
    """Get top 10 directors by movie count"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT 
            director,
            COUNT(*) as movie_count,
            ROUND(AVG(rating), 2) as avg_rating,
            MIN(year) as first_movie,
            MAX(year) as last_movie
        FROM movies 
        WHERE director IS NOT NULL AND director != ''
        GROUP BY director
        ORDER BY movie_count DESC
        LIMIT 10
    """)
    
    data = [dict(row) for row in cursor.fetchall()]
    return jsonify(data)

@app.route('/api/analytics/decade-distribution')
def get_decade_distribution():
    """Get movies by decade"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT 
            (year / 10) * 10 as decade,
            COUNT(*) as count,
            ROUND(AVG(rating), 2) as avg_rating
        FROM movies 
        GROUP BY decade
        ORDER BY decade
    """)
    
    data = [dict(row) for row in cursor.fetchall()]
    return jsonify(data)

@app.route('/api/analytics/yearly-trends')
def get_yearly_trends():
    """Get yearly movie count and average rating trends"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT 
            year,
            COUNT(*) as count,
            ROUND(AVG(rating), 2) as avg_rating
        FROM movies 
        GROUP BY year
        ORDER BY year
    """)
    
    data = [dict(row) for row in cursor.fetchall()]
    return jsonify(data)

@app.route('/api/analytics/genre-popularity')
def get_genre_popularity():
    """Get genre popularity over time (by decade)"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT 
            (year / 10) * 10 as decade,
            genre,
            COUNT(*) as count,
            ROUND(AVG(rating), 2) as avg_rating
        FROM movies 
        GROUP BY decade, genre
        ORDER BY decade, genre
    """)
    
    data = [dict(row) for row in cursor.fetchall()]
    return jsonify(data)

@app.route('/api/analytics/overview')
def get_analytics_overview():
    """Get overview statistics for analytics dashboard"""
    db = get_db()
    cursor = db.cursor()
    
    # Total movies
    cursor.execute("SELECT COUNT(*) as total FROM movies")
    total = cursor.fetchone()[0]
    
    # Average rating
    cursor.execute("SELECT ROUND(AVG(rating), 2) as avg_rating FROM movies WHERE rating IS NOT NULL")
    avg_rating = cursor.fetchone()[0] or 0
    
    # Highest rated
    cursor.execute("SELECT title, rating FROM movies ORDER BY rating DESC LIMIT 1")
    highest = cursor.fetchone()
    
    # Lowest rated
    cursor.execute("SELECT title, rating FROM movies ORDER BY rating ASC LIMIT 1")
    lowest = cursor.fetchone()
    
    # Most common genre
    cursor.execute("""
        SELECT genre, COUNT(*) as count 
        FROM movies 
        GROUP BY genre 
        ORDER BY count DESC 
        LIMIT 1
    """)
    top_genre = cursor.fetchone()
    
    # Decade with most movies
    cursor.execute("""
        SELECT (year / 10) * 10 as decade, COUNT(*) as count 
        FROM movies 
        GROUP BY decade 
        ORDER BY count DESC 
        LIMIT 1
    """)
    top_decade = cursor.fetchone()
    
    return jsonify({
        'total_movies': total,
        'avg_rating': avg_rating,
        'highest_rated': dict(highest) if highest else None,
        'lowest_rated': dict(lowest) if lowest else None,
        'most_common_genre': dict(top_genre) if top_genre else None,
        'most_movies_decade': dict(top_decade) if top_decade else None
    })

# ============================================
# FLASK ROUTES - MAIN
# ============================================

@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, '_database', None)
    if db:
        db.close()

@app.route('/')
def index():
    init_db()
    genres = get_distinct_genres()
    total_movies = get_total_movie_count()
    return render_template('index.html', genres=genres, total_movies=total_movies)

@app.route('/api/search')
def search():
    params = {
        'q': request.args.get('q', ''),
        'genre': request.args.get('genre', 'All'),
        'year_min': request.args.get('year_min', ''),
        'year_max': request.args.get('year_max', ''),
        'rating_min': request.args.get('rating_min', ''),
        'sort': request.args.get('sort', 'rating_desc')
    }
    
    query, values, total_count = build_search_query(params, include_count=True)
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute(query, values)
    results = cursor.fetchall()
    
    return jsonify({
        'results': [dict(row) for row in results],
        'count': len(results),
        'total_count': total_count
    })

# ============================================
# FLASK ROUTES - CHART DATA (Existing)
# ============================================

@app.route('/api/chart-data')
def get_chart_data():
    """Get data for charts - movies per genre and rating distribution"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT genre, COUNT(*) as count 
        FROM movies 
        GROUP BY genre 
        ORDER BY count DESC
    """)
    genre_data = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("""
        SELECT 
            ROUND(rating * 2) / 2 as rating_bucket,
            COUNT(*) as count
        FROM movies 
        WHERE rating IS NOT NULL
        GROUP BY rating_bucket
        ORDER BY rating_bucket
    """)
    rating_data = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("""
        SELECT 
            (year / 10) * 10 as decade,
            COUNT(*) as count
        FROM movies 
        GROUP BY decade
        ORDER BY decade
    """)
    decade_data = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("""
        SELECT 
            director,
            COUNT(*) as count,
            ROUND(AVG(rating), 2) as avg_rating
        FROM movies 
        WHERE director IS NOT NULL
        GROUP BY director
        ORDER BY count DESC
        LIMIT 10
    """)
    director_data = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT COUNT(*) as total FROM movies")
    total = cursor.fetchone()[0]
    
    return jsonify({
        'genre': genre_data,
        'rating': rating_data,
        'decade': decade_data,
        'director': director_data,
        'total_movies': total
    })

@app.route('/api/stats')
def get_stats():
    """Get basic stats for the header"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM movies")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT genre) as genres FROM movies")
    genres = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT director) as directors FROM movies WHERE director IS NOT NULL")
    directors = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(rating) as avg_rating FROM movies WHERE rating IS NOT NULL")
    avg_rating = cursor.fetchone()[0]
    
    return jsonify({
        'total_movies': total,
        'total_genres': genres,
        'total_directors': directors,
        'avg_rating': round(avg_rating, 2) if avg_rating else 0
    })

# ============================================
# FLASK ROUTES - CRUD OPERATIONS
# ============================================

@app.route('/api/movies', methods=['POST'])
def create_movie():
    data = request.get_json()
    
    if not data.get('title') or not data.get('year') or not data.get('genre'):
        return jsonify({'error': 'Title, year, and genre are required'}), 400
    
    try:
        title = data['title'].strip()
        year = int(data['year'])
        genre = data['genre'].strip()
        rating = float(data['rating']) if data.get('rating') else None
        director = data.get('director', '').strip() or None
        
        if year < 1888 or year > 2026:
            return jsonify({'error': 'Year must be between 1888 and 2026'}), 400
        
        if rating is not None and (rating < 0 or rating > 10):
            return jsonify({'error': 'Rating must be between 0 and 10'}), 400
        
        duplicate = check_duplicate_movie(title, year, director)
        if duplicate:
            return jsonify({
                'error': f'Duplicate movie found! "{title}" ({year}) already exists in the database.',
                'duplicate': duplicate
            }), 409
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            "INSERT INTO movies (title, year, genre, rating, director) VALUES (?, ?, ?, ?, ?)",
            (title, year, genre, rating, director)
        )
        db.commit()
        
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM movies WHERE id = ?", (new_id,))
        movie = dict(cursor.fetchone())
        
        return jsonify({
            'message': 'Movie added successfully!',
            'movie': movie
        }), 201
        
    except ValueError:
        return jsonify({'error': 'Invalid year or rating format'}), 400
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            return jsonify({
                'error': f'Duplicate movie! "{title}" ({year}) already exists in the database.'
            }), 409
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/movies/<int:movie_id>', methods=['GET'])
def get_movie(movie_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
    movie = cursor.fetchone()
    
    if movie is None:
        return jsonify({'error': 'Movie not found'}), 404
    
    return jsonify(dict(movie))

@app.route('/api/movies/<int:movie_id>', methods=['PUT'])
def update_movie(movie_id):
    data = request.get_json()
    
    if not data.get('title') or not data.get('year') or not data.get('genre'):
        return jsonify({'error': 'Title, year, and genre are required'}), 400
    
    try:
        title = data['title'].strip()
        year = int(data['year'])
        genre = data['genre'].strip()
        rating = float(data['rating']) if data.get('rating') else None
        director = data.get('director', '').strip() or None
        
        if year < 1888 or year > 2026:
            return jsonify({'error': 'Year must be between 1888 and 2026'}), 400
        
        if rating is not None and (rating < 0 or rating > 10):
            return jsonify({'error': 'Rating must be between 0 and 10'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("SELECT id FROM movies WHERE id = ?", (movie_id,))
        if cursor.fetchone() is None:
            return jsonify({'error': 'Movie not found'}), 404
        
        duplicate = check_duplicate_movie(title, year, director, exclude_id=movie_id)
        if duplicate:
            return jsonify({
                'error': f'Duplicate movie found! "{title}" ({year}) already exists in the database.',
                'duplicate': duplicate
            }), 409
        
        cursor.execute(
            """UPDATE movies 
               SET title = ?, year = ?, genre = ?, rating = ?, director = ? 
               WHERE id = ?""",
            (title, year, genre, rating, director, movie_id)
        )
        db.commit()
        
        cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
        movie = dict(cursor.fetchone())
        
        return jsonify({
            'message': 'Movie updated successfully!',
            'movie': movie
        })
        
    except ValueError:
        return jsonify({'error': 'Invalid year or rating format'}), 400
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            return jsonify({
                'error': f'Duplicate movie! "{title}" ({year}) already exists in the database.'
            }), 409
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/movies/<int:movie_id>', methods=['DELETE'])
def delete_movie(movie_id):
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("SELECT id FROM movies WHERE id = ?", (movie_id,))
        if cursor.fetchone() is None:
            return jsonify({'error': 'Movie not found'}), 404
        
        cursor.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        db.commit()
        
        return jsonify({'message': 'Movie deleted successfully!'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# RUN THE APP
# ============================================

if __name__ == '__main__':
    init_db()
    print("🚀 Server running at http://localhost:5000")
    print("📊 Chart data available at /api/chart-data")
    print("📈 Stats available at /api/stats")
    print("📝 CRUD API endpoints:")
    print("  GET  /api/search      - Search movies")
    print("  POST /api/movies      - Create movie")
    print("  GET  /api/movies/<id> - Get movie")
    print("  PUT  /api/movies/<id> - Update movie")
    print("  DELETE /api/movies/<id> - Delete movie")
    print("📊 Advanced Analytics endpoints:")
    print("  GET  /api/analytics/rating-distribution")
    print("  GET  /api/analytics/top-directors")
    print("  GET  /api/analytics/decade-distribution")
    print("  GET  /api/analytics/yearly-trends")
    print("  GET  /api/analytics/genre-popularity")
    print("  GET  /api/analytics/overview")
    app.run(debug=True, host='0.0.0.0', port=5000)