import requests
from flask import request, render_template, redirect, url_for, flash, abort, current_app
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from . import app, login_manager
from .forms import RegistrationForm, LoginForm, EditUserForm, get_genre_choices
from .user import User
import datetime
from app import app
import psycopg
from psycopg import connect, errors
import os
from werkzeug.utils import secure_filename
from .forms import DirectorForm, FilmForm, EditFilmForm, ReviewForm, CommentForm, CreateListForm, AddFilmToListForm, AddFavoriteGenreForm
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:7b"   # имя модели командой 'ollama list'
#Начальная страница
@app.route('/')
@app.route('/index')
def index():
    query = request.args.get('q', '').strip()
    films = []
    if query:
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT f.id_film, f.name, f.date, d.name AS director_name, f.poster_path
                FROM Film f
                JOIN FilmDirector d ON f.id_director = d.id_director
                WHERE f.name ILIKE %s OR d.name ILIKE %s
                ORDER BY f.name
            """, (f'%{query}%', f'%{query}%'))
            films = cur.fetchall()
    return render_template('index.html', films=films, query=query)
#Маршрут для регистрации пользователя
#Так как программа написана с использованием Mac OS, то для использования password_hash добавлен метод
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: #если пользователь уже вошел то возвращаем на индекс
        return redirect(url_for('index'))
    reg_form = RegistrationForm()
    if reg_form.validate_on_submit():
        username = reg_form.username.data
        password_hash = generate_password_hash(reg_form.password.data,method='pbkdf2:sha1', salt_length=8)
        name = reg_form.name.data
        birthday = reg_form.birthday.data
        gender = reg_form.gender.data
        role = reg_form.role.data
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            cur.execute('INSERT INTO UserProfile (username, password, name, birthday, gender, role) VALUES (%s, %s, %s, %s, %s, %s)',
                        (username, password_hash, name, birthday, gender, role))
            con.commit()
        flash(f'Регистрация {reg_form.username.data} успешна', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Регистрация', form=reg_form)
#Вход
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    login_form = LoginForm()
    if login_form.validate_on_submit():
        user = User.get_user_by_username(login_form.username.data)
        if user and check_password_hash(user.password, login_form.password.data):
            login_user(user)
            flash(f'Вы успешно вошли в систему, {current_user.username}', 'success')
            return redirect(url_for('index'))
        flash('Попытка входа неудачна', 'danger')
    return render_template('login.html', title='Вход', form=login_form)
#Выход
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
#Профиль
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    lists = []
    favorite_genres = []
    user_reviews = []
    all_genres = []                # ← добавить
    if current_user.role == 'user':
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            cur.execute('SELECT name FROM UserList WHERE id_watcher = %s ORDER BY name', (current_user.id_user,))
            lists = cur.fetchall()
            cur.execute('SELECT name FROM UserFavoriteGenre WHERE id_watcher = %s', (current_user.id_user,))
            favorite_genres = cur.fetchall()
            cur.execute('''SELECT r.id_review, r.text_review, r.date_review, f.name, f.id_film
                           FROM Review r JOIN Film f ON r.id_film = f.id_film
                           WHERE r.id_reader = %s ORDER BY r.date_review DESC''', (current_user.id_user,))
            user_reviews = cur.fetchall()
            cur.execute('SELECT name_genre FROM Genre ORDER BY name_genre')
            all_genres = cur.fetchall()
    create_list_form = CreateListForm()
    if current_user.role == 'user' and create_list_form.validate_on_submit():
        list_name = create_list_form.name.data
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            try:
                cur.execute('INSERT INTO UserList (name, id_watcher) VALUES (%s, %s)',
                            (list_name, current_user.id_user))
                con.commit()
                flash(f'Список "{list_name}" создан', 'success')
            except psycopg.errors.UniqueViolation:
                flash('Список с таким названием уже существует', 'danger')
                con.rollback()
        return redirect(url_for('profile'))

    # Форма для любимых жанров
    add_genre_form = AddFavoriteGenreForm()
    add_genre_form.genre.choices = [(g[0], g[0]) for g in all_genres]

    return render_template('profile.html', title='Профиль', lists=lists,
                           favorite_genres=favorite_genres, user_reviews=user_reviews,
                           create_list_form=create_list_form,
                           add_genre_form=add_genre_form)
#Редактирование профиля
@app.route('/edit_user/<string:username>', methods=['GET', 'POST'])
@login_required
def edit_user(username):
    if username != current_user.username:
        flash('У вас нет прав для редактирования этого пользователя.', 'danger')
        return redirect(url_for('index'))

    form = EditUserForm()
    if form.validate_on_submit():
        new_name = form.name.data
        new_birthday = form.birthday.data
        new_password_hash = generate_password_hash(form.password.data,method='pbkdf2:sha1', salt_length=8) if form.password.data else None
        #если меняют пароль его нужно вновь хэшировать с методом
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            if new_password_hash:
                cur.execute('UPDATE UserProfile SET password = %s, name = %s, birthday = %s WHERE username = %s',
                            (new_password_hash, new_name, new_birthday, username))
            else:
                cur.execute('UPDATE UserProfile SET name = %s, birthday = %s WHERE username = %s',
                            (new_name, new_birthday, username))
            con.commit()
        flash(f'Изменения для пользователя с логином {username} успешно сохранены', 'success')
        return redirect(url_for('profile'))

    return render_template('edit_user.html', title='Редактирование пользователя', form=form)

#Режиссеры
@app.route('/add_director', methods=['GET', 'POST'])
@login_required
def add_director():
    if current_user.role != 'moderator':
        flash('Только модератор может добавлять режиссёров', 'danger')
        return redirect(url_for('profile'))
    form = DirectorForm()
    if form.validate_on_submit():
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            cur.execute('INSERT INTO FilmDirector (name, birthday, gender) VALUES (%s, %s, %s)',
                        (form.name.data, form.birthday.data, form.gender.data))
            con.commit()
        flash('Режиссёр добавлен', 'success')
        return redirect(url_for('manage_directors'))
    return render_template('add_director.html', form=form)

@app.route('/edit_director/<int:director_id>', methods=['GET', 'POST'])
@login_required
def edit_director(director_id):
    if current_user.role != 'moderator':
        flash('Нет прав', 'danger')
        return redirect(url_for('profile'))
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT name, birthday, gender FROM FilmDirector WHERE id_director = %s', (director_id,))
        dir_data = cur.fetchone()
    if not dir_data:
        flash('Режиссёр не найден', 'danger')
        return redirect(url_for('manage_directors'))
    form = DirectorForm(data={'name': dir_data[0], 'birthday': dir_data[1], 'gender': dir_data[2]})
    if form.validate_on_submit():
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            cur.execute('UPDATE FilmDirector SET name=%s, birthday=%s, gender=%s WHERE id_director=%s',
                        (form.name.data, form.birthday.data, form.gender.data, director_id))
            con.commit()
        flash('Режиссёр обновлён', 'success')
        return redirect(url_for('manage_directors'))
    return render_template('edit_director.html', form=form, director_id=director_id)

@app.route('/delete_director/<int:director_id>', methods=['POST'])
@login_required
def delete_director(director_id):
    if current_user.role != 'moderator':
        flash('Нет прав', 'danger')
        return redirect(url_for('profile'))
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('DELETE FROM FilmDirector WHERE id_director = %s', (director_id,))
        con.commit()
    flash('Режиссёр удалён', 'success')
    return redirect(url_for('manage_directors'))

@app.route('/manage_directors')
@login_required
def manage_directors():
    if current_user.role != 'moderator':
        flash('Нет прав', 'danger')
        return redirect(url_for('profile'))
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT id_director, name, birthday, gender FROM FilmDirector ORDER BY name')
        directors = cur.fetchall()
    return render_template('manage_directors.html', directors=directors)

#Фильмы
@app.route('/add_film', methods=['GET', 'POST'])
@login_required
def add_film():
    if current_user.role != 'moderator':
        flash('Только модератор может добавлять фильмы', 'danger')
        return redirect(url_for('profile'))
    form = FilmForm()
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT id_director, name FROM FilmDirector ORDER BY name')
        directors = cur.fetchall()
    form.id_director.choices = [(d[0], d[1]) for d in directors]
    form.genres.choices = get_genre_choices()
    if form.validate_on_submit():
        file = form.poster.data
        filename = secure_filename(file.filename)
        base, ext = os.path.splitext(filename)
        filename = f"{base}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        relative_path = f"posters/{filename}"
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            cur.execute('INSERT INTO Film (id_director, name, description, actors, poster_path, date) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_film',
                        (form.id_director.data, form.name.data, form.description.data, form.actors.data, relative_path, form.date.data))
            film_id = cur.fetchone()[0]
            # Вставляем выбранные жанры
            for genre in form.genres.data:
                cur.execute('INSERT INTO FilmGenre (name, id_film) VALUES (%s, %s)', (genre, film_id))
            con.commit()
        flash('Фильм добавлен', 'success')
        return redirect(url_for('manage_films'))
    return render_template('add_film.html', form=form)

@app.route('/edit_film/<int:film_id>', methods=['GET', 'POST'])
@login_required
def edit_film(film_id):
    if current_user.role != 'moderator':
        flash('Нет прав', 'danger')
        return redirect(url_for('profile'))
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT id_director, name, description, actors, poster_path, date FROM Film WHERE id_film = %s', (film_id,))
        film = cur.fetchone()
        if not film:
            flash('Фильм не найден', 'danger')
            return redirect(url_for('manage_films'))
        cur.execute('SELECT name FROM FilmGenre WHERE id_film = %s', (film_id,))
        current_genres = [row[0] for row in cur.fetchall()]
    form = EditFilmForm(data={
        'name': film[1],
        'description': film[2],
        'actors': film[3],
        'date': film[5],
        'id_director': film[0],
        'genres': current_genres
    })
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT id_director, name FROM FilmDirector ORDER BY name')
        directors = cur.fetchall()
    form.id_director.choices = [(d[0], d[1]) for d in directors]
    form.genres.choices = get_genre_choices()
    if form.validate_on_submit():
        if form.poster.data:
            file = form.poster.data
            filename = secure_filename(file.filename)
            base, ext = os.path.splitext(filename)
            filename = f"{base}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            new_poster_path = f"posters/{filename}"
            old_path = os.path.join(app.static_folder, film[4])
            if os.path.exists(old_path):
                os.remove(old_path)
        else:
            new_poster_path = film[4]
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            cur.execute('UPDATE Film SET id_director=%s, name=%s, description=%s, actors=%s, poster_path=%s, date=%s WHERE id_film=%s',
                        (form.id_director.data, form.name.data, form.description.data, form.actors.data, new_poster_path, form.date.data, film_id))
            cur.execute('DELETE FROM FilmGenre WHERE id_film = %s', (film_id,))
            for genre in form.genres.data:
                cur.execute('INSERT INTO FilmGenre (name, id_film) VALUES (%s, %s)', (genre, film_id))
            con.commit()
        flash('Фильм обновлён', 'success')
        return redirect(url_for('manage_films'))
    return render_template('edit_film.html', form=form, film_id=film_id)

@app.route('/delete_film/<int:film_id>', methods=['POST'])
@login_required
def delete_film(film_id):
    if current_user.role != 'moderator':
        flash('Нет прав', 'danger')
        return redirect(url_for('profile'))
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT poster_path FROM Film WHERE id_film = %s', (film_id,))
        row = cur.fetchone()
        if row:
            old_path = os.path.join(app.static_folder, row[0])
            if os.path.exists(old_path):
                os.remove(old_path)
        cur.execute('DELETE FROM Film WHERE id_film = %s', (film_id,))
        con.commit()
    flash('Фильм удалён', 'success')
    return redirect(url_for('manage_films'))

@app.route('/manage_films')
@login_required
def manage_films():
    if current_user.role != 'moderator':
        flash('Нет прав', 'danger')
        return redirect(url_for('profile'))
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('''
            SELECT f.id_film, f.name, f.date, d.name AS director_name, f.poster_path
            FROM Film f
            JOIN FilmDirector d ON f.id_director = d.id_director
            ORDER BY f.name
        ''')
        films = cur.fetchall()
    return render_template('manage_films.html', films=films)
#Страница фильма
@app.route('/film/<int:film_id>')
def film_detail(film_id):
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT * FROM Film WHERE id_film = %s', (film_id,))
        film = cur.fetchone()
        if not film:
            abort(404)
        cur.execute('SELECT name FROM FilmGenre WHERE id_film = %s', (film_id,))
        genres = [row[0] for row in cur.fetchall()]
        cur.execute('SELECT id_director, name FROM FilmDirector WHERE id_director = %s', (film[1],))
        director = cur.fetchone()
        cur.execute('''SELECT r.id_review, r.text_review, r.date_review, u.name, r.id_reader
                       FROM Review r JOIN UserProfile u ON r.id_reader = u.id_user
                       WHERE r.id_film = %s ORDER BY r.date_review DESC''', (film_id,))
        reviews = cur.fetchall()
        comments_by_review = {}
        for rev in reviews:
            cur.execute('''SELECT c.comment_text, c.date, u.name
                           FROM Comment c JOIN UserProfile u ON c.id_user = u.id_user
                           WHERE c.id_review = %s ORDER BY c.date''', (rev[0],))
            comments_by_review[rev[0]] = cur.fetchall()

    review_form = ReviewForm()
    comment_form = CommentForm()
    return render_template('film_detail.html', film=film, genres=genres, director=director,
                           reviews=reviews, comments_by_review=comments_by_review,
                           review_form=review_form, comment_form=comment_form)

@app.route('/film/<int:film_id>/review', methods=['POST'])
@login_required
def add_review(film_id):
    if current_user.role != 'user':
        flash('Только пользователи могут оставлять рецензии', 'danger')
        return redirect(url_for('film_detail', film_id=film_id))
    form = ReviewForm()
    if form.validate_on_submit():
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            cur.execute('INSERT INTO Review (id_film, id_reader, text_review, date_review) VALUES (%s, %s, %s, NOW())',
                        (film_id, current_user.id_user, form.text_review.data))
            con.commit()
        flash('Рецензия добавлена', 'success')
    return redirect(url_for('film_detail', film_id=film_id))

@app.route('/delete_review/<int:review_id>', methods=['POST'])
@login_required
def delete_review(review_id):
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT id_film, id_reader FROM Review WHERE id_review = %s', (review_id,))
        review = cur.fetchone()
        if not review:
            flash('Рецензия не найдена', 'danger')
            return redirect(url_for('index'))
        if review[1] != current_user.id_user:
            flash('Вы не можете удалить чужую рецензию', 'danger')
            return redirect(url_for('film_detail', film_id=review[0]))
        cur.execute('DELETE FROM Review WHERE id_review = %s', (review_id,))
        con.commit()
    flash('Рецензия удалена', 'success')
    return redirect(url_for('film_detail', film_id=review[0]))

@app.route('/add_comment/<int:review_id>', methods=['POST'])
@login_required
def add_comment(review_id):
    if current_user.role != 'user':
        flash('Только пользователи могут комментировать', 'danger')
        return redirect(request.referrer or url_for('index'))
    form = CommentForm()
    if form.validate_on_submit():
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            cur.execute('SELECT id_film FROM Review WHERE id_review = %s', (review_id,))
            rev = cur.fetchone()
            if not rev:
                abort(404)
            cur.execute('INSERT INTO Comment (date, id_user, comment_text, id_review) VALUES (NOW(), %s, %s, %s)',
                        (current_user.id_user, form.comment_text.data, review_id))
            con.commit()
        flash('Комментарий добавлен', 'success')
        return redirect(url_for('film_detail', film_id=rev[0]))
    return redirect(request.referrer or url_for('index'))
#Страница режиссера
@app.route('/director/<int:director_id>')
def director_detail(director_id):
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT * FROM FilmDirector WHERE id_director = %s', (director_id,))
        director = cur.fetchone()
        if not director:
            abort(404)
        cur.execute('SELECT id_film, name, date, poster_path FROM Film WHERE id_director = %s ORDER BY date', (director_id,))
        films = cur.fetchall()
    return render_template('director_detail.html', director=director, films=films)

#Удаление списка
@app.route('/delete_list/<string:list_name>', methods=['POST'])
@login_required
def delete_list(list_name):
    if current_user.role != 'user':
        flash('Нет прав', 'danger')
        return redirect(url_for('profile'))
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('DELETE FROM UserList WHERE name = %s AND id_watcher = %s',
                    (list_name, current_user.id_user))
        con.commit()
    flash(f'Список "{list_name}" удалён', 'success')
    return redirect(url_for('profile'))

#Просмотр конкретного списка
@app.route('/view_list/<string:list_name>', methods=['GET', 'POST'])
@login_required
def view_list(list_name):
    if current_user.role != 'user':
        flash('Нет прав', 'danger')
        return redirect(url_for('profile'))
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT 1 FROM UserList WHERE name = %s AND id_watcher = %s',
                    (list_name, current_user.id_user))
        if not cur.fetchone():
            flash('Список не найден', 'danger')
            return redirect(url_for('profile'))
        cur.execute('''SELECT f.id_film, f.name, f.date, f.poster_path
                       FROM FilmInList fil
                       JOIN Film f ON fil.id_film = f.id_film
                       WHERE fil.name_list = %s AND fil.id_watcher = %s
                       ORDER BY f.name''', (list_name, current_user.id_user))
        films = cur.fetchall()
        cur.execute('SELECT id_film, name FROM Film ORDER BY name')
        all_films = cur.fetchall()

    add_form = AddFilmToListForm()
    add_form.film.choices = [(f[0], f[1]) for f in all_films]
    if add_form.validate_on_submit():
        film_id = add_form.film.data
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            try:
                cur.execute('INSERT INTO FilmInList (id_film, name_list, id_watcher) VALUES (%s, %s, %s)',
                            (film_id, list_name, current_user.id_user))
                con.commit()
                flash('Фильм добавлен в список', 'success')
            except psycopg.errors.UniqueViolation:
                flash('Этот фильм уже есть в списке', 'danger')
                con.rollback()
        return redirect(url_for('view_list', list_name=list_name))

    return render_template('view_list.html', list_name=list_name, films=films, add_form=add_form)

# Удаление фильма из списка
@app.route('/remove_from_list/<string:list_name>/<int:film_id>', methods=['POST'])
@login_required
def remove_from_list(list_name, film_id):
    if current_user.role != 'user':
        flash('Нет прав', 'danger')
        return redirect(url_for('profile'))
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('DELETE FROM FilmInList WHERE id_film = %s AND name_list = %s AND id_watcher = %s',
                    (film_id, list_name, current_user.id_user))
        con.commit()
    flash('Фильм удалён из списка', 'success')
    return redirect(url_for('view_list', list_name=list_name))

@app.route('/add_favorite_genre', methods=['POST'])
@login_required
def add_favorite_genre():
    if current_user.role != 'user':
        flash('Только пользователи могут добавлять любимые жанры', 'danger')
        return redirect(url_for('profile'))
    form = AddFavoriteGenreForm()
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT name_genre FROM Genre ORDER BY name_genre')
        genres = cur.fetchall()
    form.genre.choices = [(g[0], g[0]) for g in genres]
    if form.validate_on_submit():
        genre_name = form.genre.data
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            try:
                cur.execute('INSERT INTO UserFavoriteGenre (id_watcher, name) VALUES (%s, %s)',
                            (current_user.id_user, genre_name))
                con.commit()
                flash(f'Жанр «{genre_name}» добавлен в любимые', 'success')
            except psycopg.errors.UniqueViolation:
                flash('Этот жанр уже есть в ваших любимых', 'danger')
                con.rollback()
    return redirect(url_for('profile'))

@app.route('/delete_favorite_genre/<string:genre_name>', methods=['POST'])
@login_required
def delete_favorite_genre(genre_name):
    if current_user.role != 'user':
        flash('Нет прав', 'danger')
        return redirect(url_for('profile'))
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('DELETE FROM UserFavoriteGenre WHERE id_watcher = %s AND name = %s',
                    (current_user.id_user, genre_name))
        con.commit()
    flash(f'Жанр «{genre_name}» удалён из любимых', 'success')
    return redirect(url_for('profile'))

def ask_ollama(messages, temperature=0.7):
    """Отправляет запрос к Ollama и возвращает текст ответа."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature}
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "").strip()
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Ollama request failed: {e}")
        return None

@app.route('/analyze_interests', methods=['GET', 'POST'])
@login_required
def analyze_interests():
    if current_user.role != 'user':
        flash('Эта функция доступна только пользователям', 'danger')
        return redirect(url_for('profile'))
    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT name FROM UserList WHERE id_watcher = %s ORDER BY name', (current_user.id_user,))
        lists = [row[0] for row in cur.fetchall()]
    result_text = None
    if request.method == 'POST':
        list_name = request.form.get('list_name')
        if not list_name:
            flash('Выберите список', 'danger')
            return redirect(url_for('analyze_interests'))
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            cur.execute('''
                SELECT f.name, d.name AS director, array_agg(fg.name) as genres
                FROM FilmInList fil
                JOIN Film f ON fil.id_film = f.id_film
                JOIN FilmDirector d ON f.id_director = d.id_director
                LEFT JOIN FilmGenre fg ON f.id_film = fg.id_film
                WHERE fil.name_list = %s AND fil.id_watcher = %s
                GROUP BY f.id_film, d.name
                ORDER BY f.name
            ''', (list_name, current_user.id_user))
            films_data = cur.fetchall()
        if not films_data:
            flash('В этом списке нет фильмов', 'info')
            return redirect(url_for('analyze_interests'))
        # Формируем текст для промта
        film_lines = []
        for name, director, genres in films_data:
            genre_str = ", ".join(g for g in genres if g) if genres else "нет жанров"
            film_lines.append(f"• {name} (реж. {director}) — жанры: {genre_str}")
        films_text = "\n".join(film_lines)

        prompt = (
            "Ты — аналитик киновкусов. На основе списка фильмов и их жанров опиши интересы пользователя: "
            "предпочитаемые жанры, режиссёров, настроение, возможный характер. Будь дружелюбным и краток (3-5 предложений). "
            "Используй следующие данные:\n" + films_text
        )
        messages = [{"role": "user", "content": prompt}]
        answer = ask_ollama(messages)
        if answer is None:
            flash('Не удалось получить ответ от Ollama. Проверьте, запущен ли сервис.', 'danger')
            result_text = "Ошибка связи с аналитическим сервисом."
        else:
            result_text = answer
    return render_template('analyze_interests.html', lists=lists, result=result_text)

@app.route('/recommendations', methods=['GET', 'POST'])
@login_required
def recommendations():
    if current_user.role != 'user':
        flash('Эта функция доступна только пользователям', 'danger')
        return redirect(url_for('profile'))

    with psycopg.connect(host=app.config['DB_HOST'],
                         user=app.config['DB_USER'],
                         password=app.config['DB_PASSWORD'],
                         dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT name_genre FROM Genre ORDER BY name_genre')
        genre_list = [row[0] for row in cur.fetchall()]

    films = []
    search_method = None
    description = ""

    if request.method == 'POST':
        if 'by_favorites' in request.form:
            search_method = 'favorites'
            with psycopg.connect(host=app.config['DB_HOST'],
                                 user=app.config['DB_USER'],
                                 password=app.config['DB_PASSWORD'],
                                 dbname=app.config['DB_NAME']) as con:
                cur = con.cursor()
                cur.execute('SELECT name FROM UserFavoriteGenre WHERE id_watcher = %s', (current_user.id_user,))
                fav_genres = [row[0] for row in cur.fetchall()]

                if not fav_genres:
                    flash('Сначала добавьте любимые жанры в профиле', 'info')
                else:
                    cur.execute('''
                        SELECT DISTINCT f.id_film, f.name, f.date, f.poster_path
                        FROM Film f
                        JOIN FilmGenre fg ON f.id_film = fg.id_film
                        WHERE fg.name = ANY(%s)
                        ORDER BY f.name
                    ''', (fav_genres,))   # psycopg 3 требует список
                    films = cur.fetchall()
                    if not films:
                        flash('Фильмов с такими жанрами не найдено. Ждите пополнения каталога.', 'info')

        elif 'by_description' in request.form:
            description = request.form.get('description', '').strip()
            if not description:
                flash('Введите описание', 'danger')
            else:
                search_method = 'description'
                genre_str = ", ".join(genre_list)
                prompt = (
                    f"Ты — помощник подбора фильмов. Пользователь описал, что хочет посмотреть: "
                    f"«{description}».\n"
                    f"Из приведённого ниже списка жанров выбери те, которые точно соответствуют запросу. "
                    f"Верни **только** названия жанров через запятую, без лишних слов и пояснений.\n"
                    f"Список доступных жанров: {genre_str}\n"
                    f"Жанры:"
                )
                messages = [{"role": "user", "content": prompt}]
                answer = ask_ollama(messages)
                if answer is None:
                    flash('Не удалось связаться с Ollama для анализа описания.', 'danger')
                else:
                    guessed_genres = [g.strip().capitalize() for g in answer.split(',') if g.strip()]
                    valid_genres = [g for g in guessed_genres if g in genre_list]
                    if not valid_genres:
                        flash('Не удалось определить подходящие жанры по вашему описанию. Попробуйте уточнить.', 'warning')
                    else:
                        with psycopg.connect(host=app.config['DB_HOST'],
                                             user=app.config['DB_USER'],
                                             password=app.config['DB_PASSWORD'],
                                             dbname=app.config['DB_NAME']) as con:
                            cur = con.cursor()
                            cur.execute('''
                                SELECT DISTINCT f.id_film, f.name, f.date, f.poster_path
                                FROM Film f
                                JOIN FilmGenre fg ON f.id_film = fg.id_film
                                WHERE fg.name = ANY(%s)
                                ORDER BY f.name
                            ''', (valid_genres,))
                            films = cur.fetchall()
                        if not films:
                            flash('На данный момент в каталоге нет подходящих фильмов, но Вы можете подождать, пока их добавят модераторы.', 'info')
                        else:
                            flash(f'Найдены фильмы по жанрам: {", ".join(valid_genres)}', 'success')

    return render_template('recommendations.html', films=films, search_method=search_method,
                           description=description, genre_list=genre_list)