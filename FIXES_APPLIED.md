# Fixes Applied to Media Generator Application

## Date: January 7, 2026

### Issue 1: Workflow Script Initialization Error

**Problem**: Script failed with `NameError: name 'has_manager' is not defined`

**Root Cause**: ComfyUI-SaveAsScript generated code didn't initialize the `has_manager` variable at module level

**Fix Applied**: Added initialization to `Z-Image-Turbo-Tshirt_APP.py`
```python
# Line 11
has_manager = False
```

---

### Issue 2: Missing ComfyUI Directory Argument

**Problem**: Workflow script couldn't find ComfyUI installation

**Root Cause**: Script needs `--comfyui-directory` argument to locate dependencies

**Fix Applied**: Updated `executors.py` to pass ComfyUI directory
- Modified `ImageWorkflowExecutor.generate()` line 113
- Modified `AudioWorkflowExecutor.generate()` line 232
```python
'--comfyui-directory', str(self.comfyui_directory),
```

---

### Issue 3: Wrong Output Directory Configuration

**Problem**: Images generated to wrong location, frontend couldn't find them

**Root Cause**:
- Config had: `/Volumes/Tikbalang2TB/Users/tikbalang/comfy_env/ComfyUI/output/poets`
- API expected: `/Volumes/Tikbalang2TB/ComfyUIOutput`

**Fix Applied**: Updated `media_generator_config.json` line 9
```json
"output_directory": "/Volumes/Tikbalang2TB/ComfyUIOutput"
```

Created missing `image/` subdirectory:
```bash
mkdir -p /Volumes/Tikbalang2TB/ComfyUIOutput/image
```

---

### Issue 4: Incorrect Path Calculation

**Problem**: Database paths included `poets/` prefix which API didn't expect

**Root Cause**: `_get_relative_path()` was calculating path from parent directory

**Fix Applied**: Updated `executors.py` line 67
```python
# Changed from:
return str(full_path.relative_to(self.output_root.parent))

# Changed to:
return str(full_path.relative_to(self.output_root))
```

Now returns: `image/123_20260107/file.png` instead of `poets/image/123_20260107/file.png`

---

### Issue 5: SQLite WAL Mode Docker Visibility

**Problem**: Docker API container couldn't see newly created artifacts

**Root Cause**: SQLite WAL (Write-Ahead Logging) mode keeps uncommitted changes in separate `-wal` file. Docker container only saw the main database file until WAL checkpoint occurred.

**Fix Applied**: Added automatic WAL checkpointing to `repositories.py`

**PromptRepository.update_artifact_status()** - Line 149:
```python
conn.commit()
# Checkpoint WAL to ensure Docker containers can see changes
cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
```

**ArtifactRepository.save_artifact()** - Line 256:
```python
conn.commit()
# Checkpoint WAL to ensure Docker containers can see changes
cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
```

**Why PASSIVE checkpoint?**
- Doesn't block other connections
- Allows concurrent reads/writes
- Ensures changes are visible to Docker containers
- Balances performance with visibility

---

## System Architecture

### Directory Structure

**Output Directory**: `/Volumes/Tikbalang2TB/ComfyUIOutput`
```
ComfyUIOutput/
├── image/
│   └── {prompt_id}_{timestamp}/
│       └── output.png
└── audio/
    └── {prompt_id}_{timestamp}/
        └── generated_song.mp3
```

### Database Paths

**Database File**: `/Volumes/Tikbalang2TB/Users/tikbalang/Desktop/anthonys_musings.db`

**Docker Mount**:
- Host: `/Volumes/Tikbalang2TB/Users/tikbalang/Desktop/anthonys_musings.db`
- Container: `/app/database/anthonys_musings.db`

**Path Format in Database**: Relative to `/Volumes/Tikbalang2TB/ComfyUIOutput`
- Example: `image/201_20260107T164314/output.png`

### API Endpoints

**Media Serving**: `http://localhost:8000/api/media/{file_path}`
- Base directory: `/Volumes/Tikbalang2TB/ComfyUIOutput`
- Full path: `{base_media_dir}/{file_path}`

**Artifacts API**: `http://localhost:8000/api/prompts/{prompt_id}/artifacts`
- Returns JSON array of artifacts
- Includes file_path, metadata, timestamps

---

## Workflow Success Path

### Image Generation

```
1. User selects image prompt in GUI
2. App updates DB: artifact_status = 'processing'
3. App executes: Z-Image-Turbo-Tshirt_APP.py
   --text7 "{prompt}"
   --output /Volumes/Tikbalang2TB/ComfyUIOutput/image/{id}_{timestamp}
   --comfyui-directory /Volumes/Tikbalang2TB/Users/tikbalang/comfy_env/ComfyUI
   --queue-size 1
4. ComfyUI generates: output.png
5. App saves artifact to DB:
   - file_path: image/{id}_{timestamp}/output.png
   - preview_path: image/{id}_{timestamp}/output.png
   - metadata: {prompt, params, file_size, etc.}
   - WAL checkpoint executed
6. App updates DB: artifact_status = 'ready'
   - WAL checkpoint executed
7. Frontend fetches: /api/prompts/{id}/artifacts
8. Frontend displays: /api/media/image/{id}_{timestamp}/output.png
```

---

## Testing

### Verify Configuration
```bash
cd /Volumes/Tikbalang2TB/Users/tikbalang/comfy_env/ComfyUI/MultimediaWorkflow
python -c "from config import load_config, validate_config; config = load_config('media_generator_config.json'); issues = validate_config(config); print('Valid!' if not issues else issues)"
```

### Test Image Generation
```bash
python media_generator_app.py
# Select an image prompt
# Click "Generate Selected"
# Wait for completion
```

### Verify Frontend Display
```bash
# Check artifact API
curl http://localhost:8000/api/prompts/{id}/artifacts | jq

# Check media serving
curl -I http://localhost:8000/api/media/image/{id}_{timestamp}/output.png

# Open frontend
open http://localhost:3001
```

### Check Database WAL Checkpoint
```bash
# View WAL files
ls -lh /Volumes/Tikbalang2TB/Users/tikbalang/Desktop/anthonys_musings.db*

# Manual checkpoint if needed
sqlite3 /Volumes/Tikbalang2TB/Users/tikbalang/Desktop/anthonys_musings.db "PRAGMA wal_checkpoint(FULL);"
```

---

## Files Modified

1. `Z-Image-Turbo-Tshirt_APP.py` - Added `has_manager = False` initialization
2. `media_generator_config.json` - Changed output_directory path
3. `executors.py` - Added --comfyui-directory argument, fixed path calculation
4. `repositories.py` - Added WAL checkpoint after writes
5. `/Users/tikbalang/anthonys-musings-api/main.py` - Added backward compatibility for prompt_type filtering
6. `/Users/tikbalang/anthonys-musings-web/frontend/nginx.conf` - Reordered location blocks, excluded /api/ from static file caching

---

## Future Considerations

### Song Workflow
- Replace `song_workflow_placeholder.py` with actual ComfyUI workflow script
- Update `prompt_arg` in config if needed
- Test audio generation end-to-end

### Performance
- `PRAGMA wal_checkpoint(PASSIVE)` is non-blocking
- Consider `FULL` checkpoint for critical writes if needed
- Monitor WAL file size growth

### Monitoring
- Check WAL files don't grow too large
- Monitor Docker container logs for database errors
- Verify frontend displays new media without refresh

---

### Issue 6: Browse Page Not Showing New Image Prompts

**Problem**: Frontend Browse page "Images" filter doesn't display latest generated images

**Root Cause**: Prompt type mismatch between database and frontend query
- Old prompts in database: `prompt_type = "image"` and `"song"`
- New prompts from Media Generator: `prompt_type = "image_prompt"` and `"lyrics_prompt"`
- Frontend queries: `/api/prompts?prompt_type=image&status=completed`
- API did exact match filtering, excluding new "image_prompt" entries

**Fix Applied**: Updated API endpoint to handle backward compatibility

**File Modified**: `/Users/tikbalang/anthonys-musings-api/main.py` lines 637-648

```python
if prompt_type:
    # Handle backward compatibility: "image" should match both "image" and "image_prompt"
    # "song" should match both "song" and "lyrics_prompt"
    if prompt_type == "image":
        query += " AND (prompt_type = ? OR prompt_type = ?)"
        params.extend(["image", "image_prompt"])
    elif prompt_type == "song":
        query += " AND (prompt_type = ? OR prompt_type = ?)"
        params.extend(["song", "lyrics_prompt"])
    else:
        query += " AND prompt_type = ?"
        params.append(prompt_type)
```

**Testing**:
```bash
# Query now returns both old and new types
curl "http://localhost:8000/api/prompts?prompt_type=image&status=completed"
# Returns 43 prompts including:
#   - ID 201: prompt_type="image_prompt" (latest)
#   - ID 192: prompt_type="image" (old)

# Verify artifacts are accessible
curl "http://localhost:8000/api/prompts/201/artifacts"
# Returns artifact with file_path: "image/201_20260107T164314/output.png"

# Verify media serving works
curl "http://localhost:8000/api/media/image/201_20260107T164314/output.png"
# Returns: HTTP 200, PNG image data, 768 x 1024, 1.0M
```

**Why This Approach**:
- Maintains backward compatibility with old prompts
- Single point of change (API only, no frontend changes needed)
- Semantic correctness: "image" filter shows ALL image-related prompts
- Easy to extend for future content types

**Container Restart**:
```bash
cd /Users/tikbalang/anthonys-musings-api
docker-compose restart api
```

---

### Issue 7: Old Artifacts Still Had "poets/" Path Prefix

**Problem**: Frontend showed "Image not available" for prompt 199 despite having artifact_status='ready'

**Root Cause**: Prompt 199 was generated before Issue 3 fix was applied
- Database had path: `poets/image/199_20260107T165322/output.png`
- File existed in old location: `/ComfyUI/output/poets/image/199_20260107T165322/`
- API expected: `/Volumes/Tikbalang2TB/ComfyUIOutput/image/199_20260107T165322/`

**Fix Applied**: Migrate old artifacts to new location and update database

```bash
# Copy file from old location to new location
cp -r /Volumes/Tikbalang2TB/Users/tikbalang/comfy_env/ComfyUI/output/poets/image/199_20260107T165322 \
     /Volumes/Tikbalang2TB/ComfyUIOutput/image/

# Update database path (remove "poets/" prefix)
sqlite3 anthonys_musings.db "UPDATE prompt_artifacts
  SET file_path = 'image/199_20260107T165322/output.png',
      preview_path = 'image/199_20260107T165322/output.png'
  WHERE prompt_id = 199;"

# Checkpoint WAL for Docker visibility
sqlite3 anthonys_musings.db "PRAGMA wal_checkpoint(FULL);"
```

**Verification**:
```bash
# API now serves image correctly
curl "http://localhost:8000/api/media/image/199_20260107T165322/output.png"
# Returns: HTTP 200, PNG image data, 768 x 1024, 1.1M
```

**Note**: This only affected artifacts generated before the output directory fix. New artifacts (prompt 197, 201, etc.) already use correct paths.

---

### Issue 8: Nginx Static File Caching Intercepted Media Requests

**Problem**: Frontend still showed "Image not available" despite API serving files correctly

**Root Cause**: Nginx configuration had static file caching rule that intercepted `.png` requests
- Nginx config line 64-68 had: `location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$`
- This regex matched ALL `.png` files, including `/api/media/.../*.png` requests
- Nginx tried to serve images from local filesystem instead of proxying to API
- Result: `/api/media/image/201.../output.png` → nginx tried `/usr/share/nginx/html/api/media/...` → 404

**Investigation**:
```bash
# Direct API test worked
curl "http://localhost:8000/api/media/image/201_20260107T164314/output.png"
# Returns: HTTP 200 ✓

# Frontend proxy test failed
curl "http://localhost:3001/api/media/image/201_20260107T164314/output.png"
# Returns: HTTP 404 ✗

# Nginx logs showed it serving 404 instead of proxying
192.168.65.1 - "GET /api/media/image/201_20260107T164314/output.png HTTP/1.1" 404 26100
```

**Fix Applied**: Reordered nginx location blocks and excluded `/api/` from static file caching

**File Modified**: `/Users/tikbalang/anthonys-musings-web/frontend/nginx.conf`

**Changes**:
1. Moved `location /api/` block BEFORE static file caching (nginx processes location blocks in order)
2. Updated static file regex to exclude `/api/` paths: `location ~* ^/(?!api/).+\.(css|js|png|...)$`

**New Configuration**:
```nginx
# API proxy to existing backend - MUST come before static file caching
location /api/ {
    proxy_pass http://anthonys-musings-api-api-1:8000/api/;
    # ... proxy headers
}

# Static file caching (excludes /api/ paths which are already handled above)
location ~* ^/(?!api/).+\.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    try_files $uri =404;
}
```

**Container Restart**:
```bash
cd /Users/tikbalang/anthonys-musings-web
docker-compose restart frontend
```

**Testing**:
```bash
# Frontend proxy now works
curl "http://localhost:3001/api/media/image/201_20260107T164314/output.png"
# Returns: HTTP 200, PNG image data, 768 x 1024, 1.0M ✓

curl "http://localhost:3001/api/media/image/199_20260107T165322/output.png"
# Returns: HTTP 200, PNG image data, 768 x 1024, 1.1M ✓
```

**Why This Fix Works**:
- Nginx evaluates location blocks in specific order (exact matches, then prefix, then regex)
- By using `location /api/` (prefix match) before regex matches, API requests bypass static file handling
- The negative lookahead `(?!api/)` provides defense-in-depth to ensure static caching never catches API paths

---

## Summary

All issues resolved! The application now:
✅ Initializes workflow scripts correctly
✅ Generates images to the correct output directory
✅ Stores correct relative paths in database
✅ Checkpoints WAL for Docker visibility
✅ API serves media files correctly
✅ Browse page filters show both old and new prompt types
✅ Old artifacts migrated to correct location
✅ Nginx properly proxies media requests to API
✅ Frontend displays generated images immediately

**Complete End-to-End Workflow Working:**
1. User selects image prompt in Media Generator app → ✅
2. App generates image using ComfyUI workflow → ✅
3. Image saved to correct output directory → ✅
4. Artifact record created in database with correct path → ✅
5. Database changes visible to Docker API container → ✅
6. API endpoint serves image file → ✅
7. Frontend Browse page lists prompt → ✅
8. Nginx proxies image request to API → ✅
9. Browser displays generated image → ✅

The complete workflow from prompt selection to frontend display is now working end-to-end.
