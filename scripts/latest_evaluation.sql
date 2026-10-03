-- Latest evaluation for a conversation: summary, per-area breakdown, totals.
-- SQLite (JSON1). Change the transcript id as needed.

-- 1. Summary
SELECT id, tenant_id, project_id, conversation_transcript_id, template_id, template_version,
       analyzer, status, qualified, score, temperature, created_at
FROM evaluations
WHERE conversation_transcript_id = 'session_1790840106971_6520'
ORDER BY created_at DESC
LIMIT 1;

-- 2. Score per area against its weight
SELECT json_extract(c.value, '$.dimension')                AS area,
       json_extract(c.value, '$.weight')                   AS weight,
       ROUND(json_extract(c.value, '$.weight') * 100, 2)   AS max_points,
       json_extract(c.value, '$.ratio')                    AS ratio,
       json_extract(c.value, '$.contribution')             AS points
FROM evaluations e, json_each(e.result, '$.score_breakdown.components') c
WHERE e.id = (
    SELECT id FROM evaluations
    WHERE conversation_transcript_id = 'session_1790840106971_6520'
    ORDER BY created_at DESC LIMIT 1
);

-- 3. Totals
SELECT json_extract(result, '$.score_breakdown.raw_score')   AS raw_score,
       json_extract(result, '$.score_breakdown.penalty')     AS penalty,
       json_extract(result, '$.score_breakdown.final_score') AS final_score,
       temperature
FROM evaluations
WHERE conversation_transcript_id = 'session_1790840106971_6520'
ORDER BY created_at DESC
LIMIT 1;
