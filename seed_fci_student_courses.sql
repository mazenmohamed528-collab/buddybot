SET QUOTED_IDENTIFIER ON;
USE FCI_UNIVERSITY;
GO

-- Rebuild course-level marks from the existing FCI GPA records.
-- The source database contains semester GPA but no Student_Courses rows, so
-- these rows provide deterministic demo marks aligned to each student's GPA.
DELETE FROM Student_Courses;
DBCC CHECKIDENT ('Student_Courses', RESEED, 0);
GO

;WITH BaseEnrollments AS (
    SELECT
        s.student_id,
        c.course_id,
        g.academic_year,
        g.semester,
        c.total_marks,
        s.current_year AS original_year,
        CASE
            WHEN g.semester_gpa >= 3.95 THEN 97.0
            WHEN g.semester_gpa >= 3.70 THEN 93.0
            WHEN g.semester_gpa >= 3.40 THEN 89.0
            WHEN g.semester_gpa >= 3.20 THEN 85.0
            WHEN g.semester_gpa >= 3.00 THEN 81.0
            WHEN g.semester_gpa >= 2.80 THEN 77.0
            WHEN g.semester_gpa >= 2.60 THEN 73.0
            WHEN g.semester_gpa >= 2.40 THEN 69.0
            WHEN g.semester_gpa >= 2.20 THEN 65.0
            WHEN g.semester_gpa >= 1.50 THEN 58.0
            WHEN g.semester_gpa > 0.00 THEN 50.0
            ELSE 45.0
        END AS base_percentage,
        ((ABS(CHECKSUM(s.student_id, c.course_code, g.semester)) % 1100) / 100.0) - 5.0 AS variation
    FROM Students s
    JOIN GPA_Records g
        ON g.student_id = s.student_id
       AND g.is_baseline = 0
       AND g.semester_gpa IS NOT NULL
    JOIN Courses c
        ON c.course_year = s.current_year
       AND c.course_semester = g.semester
       AND c.dept_id = s.dept_id
)
INSERT INTO Student_Courses
    (student_id, course_id, academic_year, semester, raw_score, total_marks, is_reset, original_year, status)
SELECT
    student_id,
    course_id,
    academic_year,
    semester,
    CAST(ROUND(
        total_marks *
        CASE
            WHEN base_percentage + variation > 100.0 THEN 100.0
            WHEN base_percentage + variation < 0.0 THEN 0.0
            ELSE base_percentage + variation
        END / 100.0,
        2
    ) AS DECIMAL(6, 2)) AS raw_score,
    total_marks,
    0 AS is_reset,
    original_year,
    'completed' AS status
FROM BaseEnrollments;
GO

SELECT COUNT(*) AS SeededStudentCourseRows FROM Student_Courses;
SELECT COUNT(*) AS GradeViewRows FROM v_grades;
GO
