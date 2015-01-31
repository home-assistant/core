var gulp = require('gulp');
var watch = require('gulp-watch');
var vulcanize = require('gulp-vulcanize');
var connect = require('gulp-connect');

//dist
gulp.task('dist', function() {
    return gulp.src(['./src/*.html'])
        .pipe(vulcanize({dest: 'dist'}))
        .pipe(gulp.dest('./dist'));
});

//vendor javascript
gulp.task('vendor-scripts', function() {
    return gulp.src(['./src/bower_components/polymer-platform/platform.js'])
        .pipe(gulp.dest('./dist/demo'));
});

//dev server 
gulp.task('server', function() {
    connect.server({
        root: './dist'
    });
});

//watch task
gulp.task('watch', function() {
	gulp.watch('src/*.html', ['dist']);
});

//default
gulp.task('default', ['dist', 'vendor-scripts', 'watch', 'server']);


