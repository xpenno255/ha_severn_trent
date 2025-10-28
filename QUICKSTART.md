# Quick Start Guide - Severn Trent Integration v2.0

## For Developers: Implementation Steps

### 1. Replace Files in Your Integration

Copy these files to `custom_components/severn_trent/`:

**Modified Files (replace existing):**
- `api.py` - Updated with new fetch methods
- `config_flow.py` - Added backfill step
- `sensor.py` - Completely new sensor classes (renamed to sensor_new.py in outputs, rename back)
- `__init__.py` - New coordinator integration
- `strings.json` - Added backfill text

**New Files (add these):**
- `coordinator.py` - Core data management
- `services.yaml` - Backfill service definition

**Unchanged Files (keep as-is):**
- `const.py`
- `manifest.json` (optionally update version to 2.0.0)

### 2. Update manifest.json Version

```json
{
  "domain": "severn_trent",
  "name": "Severn Trent Water",
  "version": "2.0.0",
  ...
}
```

### 3. Test Locally

```bash
# Restart Home Assistant
ha core restart

# Check logs
ha core logs -f
```

### 4. Test Config Flow

1. Go to Settings → Devices & Services
2. Click Add Integration
3. Search "Severn Trent Water"
4. Enter test credentials
5. Verify backfill checkbox appears
6. Complete setup
7. Check all sensors appear

### 5. Test Backfill

Check Developer Tools → Statistics for:
- `severn_trent:{account}:hourly_usage`
- `severn_trent:{account}:daily_usage`
- `severn_trent:{account}:weekly_usage`
- `severn_trent:{account}:monthly_usage`

### 6. Test Service

Developer Tools → Services:
```yaml
service: severn_trent.backfill_history
data: {}
```

---

## For Users: Installation Steps

### First Time Install

1. **Install via HACS**
   - HACS → Integrations
   - Add custom repository: `https://github.com/YOUR_REPO`
   - Install "Severn Trent Water"

2. **Restart Home Assistant**
   - Settings → System → Restart

3. **Add Integration**
   - Settings → Devices & Services
   - Add Integration
   - Search "Severn Trent Water"

4. **Enter Credentials**
   - Email: Your Severn Trent account email
   - Password: Your Severn Trent password

5. **Select Account** (if multiple)

6. **Enable Backfill** ✅
   - Check "Backfill historical data"
   - This imports last 7 days hourly, 60 days daily data
   - Takes 1-2 minutes

7. **Wait for Setup**
   - Integration will appear in Devices & Services
   - 7 sensors will be created
   - Statistics will be populated

### Upgrading from v1.x

1. **Backup First!**
   - Settings → System → Backups
   - Create full backup

2. **Remove Old Integration**
   - Settings → Devices & Services
   - Find Severn Trent Water
   - Click "..." → Remove Integration

3. **Update Code**
   - HACS will show update available
   - Click Update
   - Or manually replace files

4. **Restart Home Assistant**

5. **Re-add Integration** (follow first-time install steps)

6. **Update Automations**
   - Replace sensor entity IDs:
     - `yesterday_usage` → `previous_day_usage`
     - `weekly_total` → `week_to_date`
     - `daily_average` → removed (calculate from stats)

---

## Quick Test Script

### Check Everything Works

```yaml
# Developer Tools → Template
# Paste this and click "Render"

Previous Day: {{ states('sensor.severn_trent_previous_day_usage') }} m³
Week to Date: {{ states('sensor.severn_trent_week_to_date') }} m³
Month to Date: {{ states('sensor.severn_trent_month_to_date') }} m³
Overnight: {{ states('sensor.severn_trent_overnight_usage') }} m³
Leak Alert: {{ states('binary_sensor.severn_trent_overnight_leak_alert') }}
Meter Reading: {{ states('sensor.severn_trent_meter_reading') }} m³
Estimated: {{ states('sensor.severn_trent_estimated_meter_reading') }} m³

Last Update: {{ state_attr('sensor.severn_trent_previous_day_usage', 'last_update') }}
```

Expected output:
```
Previous Day: 0.395 m³
Week to Date: 2.156 m³
Month to Date: 7.619 m³
Overnight: 0.008 m³
Leak Alert: off
Meter Reading: 1234.567 m³
Estimated: 1242.186 m³

Last Update: 2025-10-27
```

---

## Expected Behavior Timeline

### Day 0 (Installation Day)
**Time:** 2:00 PM
- ✅ Integration added
- ✅ Backfill started
- ✅ Backfill completed (2 mins)
- ✅ All sensors created
- ⚠️ Some sensors show "Unknown" (waiting for 6am update)
- ✅ Statistics visible in Developer Tools

### Day 1 (First Full Day)
**Time:** 6:00 AM
- ✅ First scheduled update runs
- ✅ Previous Day sensor updates (shows Day 0 usage)
- ✅ Week to Date updates
- ✅ Month to Date updates
- ✅ Overnight Usage updates (2am-5am from Day 0)
- ✅ Overnight Leak Alert updates
- ✅ Hourly statistics added for Day 0
- ✅ Daily statistic added for Day 0

**Time:** 10:00 AM (Verify)
- Check logs: "Successfully updated data for 2025-10-27"
- Check sensors: All should have values
- Check statistics: New entries for yesterday

### Day 2-7 (Normal Operation)
**Time:** 6:00 AM daily
- ✅ Update runs
- ✅ All sensors update
- ✅ Statistics accumulate
- ✅ Week to Date increases

### Week 2 (Monday 6:00 AM)
- ✅ Update runs
- ✅ Week to Date **resets** to Day 1 only
- ✅ Weekly statistic created for previous week

---

## Troubleshooting Quick Reference

### Problem: Sensors show "Unknown"

**Solution:**
```yaml
# Check coordinator status
{{ state_attr('sensor.severn_trent_previous_day_usage', 'last_update') }}

# If None, run backfill manually
service: severn_trent.backfill_history
data: {}
```

### Problem: No statistics in Developer Tools

**Check:**
1. Developer Tools → Statistics
2. Search "severn_trent"
3. Should see 4 statistics IDs

**Fix:**
```yaml
# Re-run backfill
service: severn_trent.backfill_history
data: {}
```

### Problem: Update not running at 6am

**Check logs at 6:05am:**
```
[custom_components.severn_trent.coordinator] Successfully updated data for 2025-10-27
[custom_components.severn_trent.coordinator] Injected 24 hourly statistics
```

**If missing:**
- Check Home Assistant is running
- Check integration is enabled
- Check logs for errors

### Problem: Authentication fails

**Solution:**
1. Verify credentials in Severn Trent app
2. Remove integration
3. Re-add with correct credentials

### Problem: Overnight Leak always OFF

**This is normal if:**
- Less than 24 hours since setup (no overnight period yet)
- Actual overnight usage < 0.01m³

**Check:**
```yaml
{{ state_attr('binary_sensor.severn_trent_overnight_leak_alert', 'overnight_usage') }}
```

---

## Daily Checklist (for testing)

### Day 1 (Installation)
- [ ] Integration installed
- [ ] Backfill completed
- [ ] 7 sensors created
- [ ] 4 statistics entities exist
- [ ] Manual readings visible

### Day 2 (First Update)
- [ ] 6am update ran
- [ ] Previous Day shows yesterday
- [ ] Week to Date > 0
- [ ] Month to Date > 0
- [ ] Overnight Usage calculated
- [ ] Hourly statistics added

### Week 2 (First Monday)
- [ ] Week to Date reset
- [ ] Weekly statistic created
- [ ] All other sensors work

---

## File Checklist

Before deploying, verify these files exist:

```
custom_components/severn_trent/
├── __init__.py           ✅ Modified - coordinator integration
├── api.py                ✅ Modified - new fetch methods
├── config_flow.py        ✅ Modified - backfill step
├── const.py              ⚪ Unchanged
├── coordinator.py        ✅ NEW - data coordinator
├── manifest.json         ⚪ Unchanged (update version)
├── sensor.py             ✅ Modified - new sensors
├── services.yaml         ✅ NEW - service definition
└── strings.json          ✅ Modified - backfill text
```

---

## Integration Health Check

Run this after 24 hours:

```yaml
# Developer Tools → Services
service: logger.set_level
data:
  custom_components.severn_trent: debug

# Wait 1 minute, then check logs for:
# - Coordinator status
# - Last successful update
# - Statistics count
# - Any errors
```

Expected healthy logs:
```
[coordinator] Last successful update: 2025-10-27
[coordinator] Fetch status: success
[coordinator] Missing dates: []
[coordinator] Injected 24 hourly statistics
[coordinator] Injected 1 daily statistics
```

---

## Quick Links

- **Full Documentation:** README.md
- **Implementation Details:** IMPLEMENTATION_SUMMARY.md
- **GitHub Issues:** [Your repo]/issues
- **Community Forum:** [Forum link]

---

## Need Help?

### For Developers
1. Check IMPLEMENTATION_SUMMARY.md
2. Review coordinator.py comments
3. Enable debug logging
4. Check GitHub issues

### For Users
1. Check README.md
2. Enable debug logging
3. Post logs in community forum
4. Create GitHub issue with logs

---

## Success Criteria

Your integration is working correctly when:

✅ All 7 sensors have values after 6am update
✅ Statistics visible in Developer Tools (4 types)
✅ Previous Day matches yesterday's usage
✅ Week to Date resets on Monday
✅ Month to Date increases daily
✅ Overnight Leak detects usage > 0.01m³
✅ Estimated Meter increases daily
✅ No errors in logs after 6am update

---

## Next Steps After Installation

1. **Add to Energy Dashboard**
   - Settings → Dashboards → Energy
   - Add Water source
   - Select `severn_trent:{account}:daily_usage`

2. **Create Automations**
   - Weekly usage reports
   - Leak alerts
   - High usage notifications

3. **Add to Lovelace**
   - Water usage history card
   - Current week card
   - Leak alert card

4. **Monitor for a Week**
   - Verify updates run at 6am
   - Check Week to Date resets Monday
   - Verify statistics accumulate

---

That's it! Your Severn Trent integration v2.0 is ready to use. 🎉
