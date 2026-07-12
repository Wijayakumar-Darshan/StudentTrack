-- CreateTable
CREATE TABLE "users" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "username" TEXT NOT NULL,
    "password_hash" TEXT NOT NULL,
    "full_name" TEXT,
    "role" TEXT NOT NULL,
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "streams" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL
);

-- CreateTable
CREATE TABLE "subjects" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL,
    "stream_id" INTEGER NOT NULL,
    CONSTRAINT "subjects_stream_id_fkey" FOREIGN KEY ("stream_id") REFERENCES "streams" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "careers" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL,
    "stream_id" INTEGER NOT NULL,
    CONSTRAINT "careers_stream_id_fkey" FOREIGN KEY ("stream_id") REFERENCES "streams" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "career_cutoffs" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "career_id" INTEGER NOT NULL,
    "subject_id" INTEGER NOT NULL,
    "min_marks" REAL NOT NULL,
    CONSTRAINT "career_cutoffs_career_id_fkey" FOREIGN KEY ("career_id") REFERENCES "careers" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "career_cutoffs_subject_id_fkey" FOREIGN KEY ("subject_id") REFERENCES "subjects" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "students" (
    "reg_no" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "grade" INTEGER NOT NULL DEFAULT 10,
    "class_section" TEXT NOT NULL DEFAULT 'A',
    "stream_id" INTEGER,
    "career_id" INTEGER,
    CONSTRAINT "students_stream_id_fkey" FOREIGN KEY ("stream_id") REFERENCES "streams" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "students_career_id_fkey" FOREIGN KEY ("career_id") REFERENCES "careers" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "marks" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "reg_no" TEXT NOT NULL,
    "subject_id" INTEGER NOT NULL,
    "term" INTEGER NOT NULL,
    "year" INTEGER NOT NULL,
    "grade" INTEGER NOT NULL DEFAULT 10,
    "marks" REAL NOT NULL,
    CONSTRAINT "marks_reg_no_fkey" FOREIGN KEY ("reg_no") REFERENCES "students" ("reg_no") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "marks_subject_id_fkey" FOREIGN KEY ("subject_id") REFERENCES "subjects" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "users_username_key" ON "users"("username");

-- CreateIndex
CREATE UNIQUE INDEX "streams_name_key" ON "streams"("name");

-- CreateIndex
CREATE UNIQUE INDEX "subjects_name_stream_id_key" ON "subjects"("name", "stream_id");

-- CreateIndex
CREATE UNIQUE INDEX "careers_name_stream_id_key" ON "careers"("name", "stream_id");

-- CreateIndex
CREATE UNIQUE INDEX "career_cutoffs_career_id_subject_id_key" ON "career_cutoffs"("career_id", "subject_id");

-- CreateIndex
CREATE UNIQUE INDEX "marks_reg_no_subject_id_term_year_key" ON "marks"("reg_no", "subject_id", "term", "year");
