/**
 * Remove all UDF fields from a specified SDP instance (portal) in the same org.
 * Run in browser console while logged into any SDP instance in the org (Admin or with UDF delete permission).
 *
 * Usage: Paste this script in the browser console, run. You will be asked for the portal id
 * of the instance from which to delete UDFs.
 *
 * Set module to clean: 'request' | 'problem' | 'change'
 */
var MODULE_TO_CLEAN = 'request';

(function () {
  var portalId = prompt('Enter the portal id (app id) of the instance from which to DELETE UDFs:');
  if (!portalId || portalId.trim() === '') {
    console.log('Cancelled. No portal id provided.');
    return;
  }
  portalId = portalId.trim();

  var failedDeletes = [];
  var deletedCount = 0;
  var module = typeof MODULE_TO_CLEAN !== 'undefined' ? MODULE_TO_CLEAN : 'request';

  function getCsrfHeaders() {
    var headers = {
      'Accept': 'application/vnd.manageengine.sdp.v3+json',
      'x-sdpod-appid': portalId
    };
    if (typeof csrfParamName !== 'undefined' && typeof csrfParamValue !== 'undefined') {
      headers['X-ZCSRF-TOKEN'] = csrfParamName + '=' + csrfParamValue;
    }
    return headers;
  }

  function deleteUdf(id, displayName, index, udfList) {
    var url = '/api/v3/udf_fields/' + id;
    var opts = {
      method: 'DELETE',
      credentials: 'same-origin',
      headers: getCsrfHeaders()
    };

    fetch(url, opts)
      .then(function (res) {
        if (res.ok) {
          deletedCount++;
          console.log('[OK] Deleted UDF: ' + displayName + ' (id: ' + id + ')');
        } else {
          failedDeletes.push({ id: id, name: displayName, status: res.status });
          console.warn('[FAIL] ' + displayName + ' (id: ' + id + ') status: ' + res.status);
        }
      })
      .catch(function (err) {
        failedDeletes.push({ id: id, name: displayName, error: err.message });
        console.warn('[ERROR] ' + displayName + ' (id: ' + id + '): ' + err.message);
      })
      .finally(function () {
        processNext(index, udfList);
      });
  }

  function processNext(index, udfList) {
    if (index >= udfList.length) {
      console.log('--- Done. Deleted: ' + deletedCount + ', Failed: ' + failedDeletes.length + ' ---');
      if (failedDeletes.length) {
        console.log('Failed to delete:', failedDeletes);
      }
      return;
    }
    var item = udfList[index];
    deleteUdf(item.id, item.display_name, index + 1, udfList);
  }

  function run() {
    var url = '/api/v3/' + module + 's/_metainfo';
    var opts = {
      method: 'GET',
      credentials: 'same-origin',
      headers: getCsrfHeaders()
    };

    fetch(url, opts)
      .then(function (res) {
        if (!res.ok) {
          throw new Error('Metainfo failed: ' + res.status + ' ' + res.statusText);
        }
        return res.json();
      })
      .then(function (data) {
        var udfFields = (data.metainfo && data.metainfo.fields && data.metainfo.fields.udf_fields && data.metainfo.fields.udf_fields.fields) || {};
        var udfList = [];
        Object.keys(udfFields).forEach(function (key) {
          var f = udfFields[key];
          if (f && f.id) {
            udfList.push({
              id: f.id,
              display_name: f.display_name || key
            });
          }
        });

        if (udfList.length === 0) {
          console.log('No UDF fields found for module: ' + module + '.');
          return;
        }

        var msg = 'Portal id: ' + portalId + '\nModule to clean: ' + module + '\nUDFs found: ' + udfList.length + '\nProceed to delete all in this instance?';
        if (!confirm(msg)) {
          console.log('Cancelled. No UDFs deleted.');
          return;
        }
        console.log('Module: ' + module + '. Deleting ' + udfList.length + ' UDF(s)...');
        processNext(0, udfList);
      })
      .catch(function (err) {
        console.error('Error:', err.message);
      });
  }

  run();
})();
