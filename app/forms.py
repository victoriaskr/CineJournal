from flask_wtf import FlaskForm
from wtforms import TextAreaField, BooleanField, StringField, DateField, IntegerField, PasswordField, SubmitField, SelectField, validators
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import SelectMultipleField
from wtforms.widgets import ListWidget, CheckboxInput

class RegistrationForm(FlaskForm):
    username = StringField('Логин', [validators.Length(min=4, max=25)])
    password = PasswordField('Пароль', [validators.InputRequired(),
                                        validators.Length(min=6, max=100),
                                        validators.EqualTo('confirm', message='Пароли должны совпадать')])
    confirm  = PasswordField('Повторите пароль')
    name = StringField('Имя', validators=[validators.InputRequired(), validators.Length(min=2, max=255)])
    birthday = DateField('День рождения', format='%Y-%m-%d', validators=[validators.InputRequired()])
    gender = SelectField('Пол', choices=[('male', 'Male'), ('female', 'Female')], validators=[validators.InputRequired()]) #первое значение для даты, второе для выпадающего списка
    role = SelectField('Роль', choices=[('user', 'User'), ('moderator', 'Moderator')], validators=[validators.InputRequired()]) #аналогично с user, moderator
    submit = SubmitField('Зарегистрироваться')

class LoginForm(FlaskForm):
    username = StringField('Логин', [validators.Length(min=4, max=25)])
    password = PasswordField('Пароль', [validators.InputRequired(),
                                         validators.Length(min=6, max=100)])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

class EditUserForm(FlaskForm):
    username = StringField('Логин', [validators.Length(min=4, max=25)])
    name = StringField('Имя', validators=[validators.InputRequired(), validators.Length(min=2, max=255)])
    birthday = DateField('День рождения', format='%Y-%m-%d', validators=[validators.InputRequired()])
    password = PasswordField('Пароль', [validators.Length(min=6, max=100)])
    submit = SubmitField('Сохранить изменения')
# Выбор жанров с чекбоксами (удобнее, чем зажатый Ctrl)
class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

# Функция для динамической загрузки списка жанров из БД
def get_genre_choices():
    import psycopg
    from flask import current_app
    try:
        with psycopg.connect(host=current_app.config['DB_HOST'],
                             user=current_app.config['DB_USER'],
                             password=current_app.config['DB_PASSWORD'],
                             dbname=current_app.config['DB_NAME']) as con:
            cur = con.cursor()
            cur.execute('SELECT name_genre FROM Genre ORDER BY name_genre')
            genres = cur.fetchall()
        return [(g[0], g[0]) for g in genres]
    except:
        return []

# Форма добавления / редактирования режиссёра
class DirectorForm(FlaskForm):
    name = StringField('Имя', validators=[validators.InputRequired(), validators.Length(min=2, max=255)])
    birthday = DateField('Дата рождения', format='%Y-%m-%d', validators=[validators.InputRequired()])
    gender = SelectField('Пол', choices=[('male', 'Мужской'), ('female', 'Женский')], validators=[validators.InputRequired()])
    submit = SubmitField('Сохранить')

# Форма добавления фильма (загрузка постера обязательна)
class FilmForm(FlaskForm):
    name = StringField('Название', validators=[validators.InputRequired(), validators.Length(min=1, max=255)])
    description = TextAreaField('Описание', validators=[validators.InputRequired()])
    actors = TextAreaField('Актёры (через запятую)', validators=[validators.InputRequired()])
    date = IntegerField('Год выпуска', validators=[validators.InputRequired()])
    id_director = SelectField('Режиссёр', coerce=int, validators=[validators.InputRequired()])
    # Жанры – чекбоксы
    genres = MultiCheckboxField('Жанры')
    # Постер – обязателен при создании
    poster = FileField('Постер (изображение)', validators=[
        FileRequired(message='Загрузите постер'),
        FileAllowed(['jpg', 'jpeg', 'png'], 'Только изображения (jpg, jpeg, png)')
    ])
    submit = SubmitField('Добавить фильм')

# Форма редактирования фильма (постер не обязателен)
class EditFilmForm(FlaskForm):
    name = StringField('Название', validators=[validators.InputRequired(), validators.Length(min=1, max=255)])
    description = TextAreaField('Описание', validators=[validators.InputRequired()])
    actors = TextAreaField('Актёры (через запятую)', validators=[validators.InputRequired()])
    date = IntegerField('Год выпуска', validators=[validators.InputRequired()])
    id_director = SelectField('Режиссёр', coerce=int, validators=[validators.InputRequired()])
    genres = MultiCheckboxField('Жанры')
    poster = FileField('Новый постер (если нужно заменить)', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Только изображения')
    ])
    submit = SubmitField('Сохранить изменения')

class ReviewForm(FlaskForm):
    text_review = TextAreaField('Ваша рецензия', validators=[validators.InputRequired()])
    submit = SubmitField('Отправить рецензию')

class CommentForm(FlaskForm):
    comment_text = TextAreaField('Комментарий', validators=[validators.InputRequired()])
    submit = SubmitField('Оставить комментарий')

class CreateListForm(FlaskForm):
    name = StringField('Название списка', validators=[validators.InputRequired(), validators.Length(min=1, max=255)])
    submit = SubmitField('Создать список')

class AddFilmToListForm(FlaskForm):
    film = SelectField('Добавить фильм', coerce=int, validators=[validators.InputRequired()])
    submit = SubmitField('Добавить')

class AddFavoriteGenreForm(FlaskForm):
    genre = SelectField('Жанр', validators=[validators.InputRequired()])
    submit = SubmitField('Добавить жанр')